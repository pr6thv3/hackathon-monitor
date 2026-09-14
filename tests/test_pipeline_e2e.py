"""
End-to-end integration test for Hackathon Monitor v4 Transformation Pipeline.

Tests the full 5-stage workflow:
1. Configuration loading & preference profile resolution
2. SQLite database initialization, TTL expiration, & migration
3. Multi-source ingestion & Stage 1 event extraction
4. Memory deduplication against seen events
5. Stage 2 Dual Scoring (SOS for college portals, FOS for global platforms)
6. Stage 3 Personalized Relevance evaluation
7. Stage 4 Composite Ranking & quality gating
8. Stage 5 Telegram notification formatting & Markdown report generation
9. Persistence to SQLite & JSON synchronization
"""

import os
import json
import pytest
from datetime import datetime, timezone, timedelta
from unittest.mock import patch, MagicMock

from src.config import load_config
from src.db import init_db, upsert_event, save_event_score, get_connection, sync_sqlite_to_seen_events_json
from src.memory import clean_expired_events, is_new, mark_seen, _hash_title
from src.notifier import format_notification
from src.report import generate_report
from main import calculate_composite_rank


@pytest.fixture
def test_env(tmp_path):
    """Set up temporary directory and files for end-to-end pipeline test."""
    db_file = str(tmp_path / "test_monitor.db")
    memory_file = str(tmp_path / "test_seen_events.json")
    reports_dir = str(tmp_path / "reports")
    os.makedirs(reports_dir, exist_ok=True)

    init_db(db_file)

    return {
        "db_path": db_file,
        "memory_path": memory_file,
        "reports_dir": reports_dir,
    }


def test_full_v4_pipeline_e2e(test_env):
    """Execute and verify the full v4 pipeline flow."""
    db_path = test_env["db_path"]
    memory_path = test_env["memory_path"]
    reports_dir = test_env["reports_dir"]

    # 1. Verify Configuration & Preference Profile
    cfg = load_config("config.yaml")
    assert cfg.user_name == "Preethve"
    assert cfg.preference_profile is not None
    assert "hackathon" in cfg.preference_profile.wanted_event_types or len(cfg.preference_profile.topics) > 0

    # 2. TTL Expiry & Deduplication Memory Setup
    now = datetime.now(timezone.utc)
    old_title = "Old Hackathon from 100 days ago"
    seen_title = "Already Seen AI Hackathon"

    raw_memory = {
        _hash_title(old_title): {
            "title": old_title,
            "date_first_seen": (now - timedelta(days=100)).isoformat(),
            "source": "devpost",
        },
        _hash_title(seen_title): {
            "title": seen_title,
            "date_first_seen": (now - timedelta(days=5)).isoformat(),
            "source": "devpost",
        }
    }
    cleaned_memory, removed_count = clean_expired_events(raw_memory, ttl_days=90)
    assert removed_count == 1
    assert _hash_title(old_title) not in cleaned_memory
    assert _hash_title(seen_title) in cleaned_memory

    # 3. Simulate Extracted Events (Stage 1 Output)
    extracted_events = [
        {
            "title": "Already Seen AI Hackathon",
            "event_type": "hackathon",
            "source": "devpost",
            "source_type": "global_platform",
            "link": "https://devpost.com/seen-ai",
            "registration_deadline": "3 days left",
        },
        {
            "title": "Global Autonomous Agent Challenge",
            "event_type": "hackathon",
            "source": "devpost",
            "source_type": "global_platform",
            "link": "https://devpost.com/agent-challenge",
            "registration_deadline": "5 days left",
            "mode": "online",
            "prize_pool": "$50,000",
            "sponsors": ["OpenAI", "Anthropic"],
            "description": "Build agentic AI workflows.",
            "tags": ["AI", "agents", "python"],
        },
        {
            "title": "VIT Chennai CODELYMPICS 2026",
            "event_type": "hackathon",
            "source": "vit_eventhub",
            "source_type": "college_portal",
            "link": "https://eventhubcc.vit.ac.in/event/codelympics",
            "registration_deadline": "6 days left",
            "mode": "offline",
            "prize_pool": "₹25,000 + Trophies",
            "sponsors": ["ACM Student Chapter"],
            "description": "Competitive college programming and hackathon.",
            "tags": ["algorithms", "coding", "systems"],
        },
        {
            "title": "Low Quality Spam Contest",
            "event_type": "competition",
            "source": "unstop",
            "source_type": "global_platform",
            "link": None,
            "registration_deadline": "40 days left",
            "sponsors": [],
            "description": "Basic quiz.",
            "tags": ["quiz"],
        }
    ]

    # 4. Memory Deduplication
    new_events = [e for e in extracted_events if is_new(cleaned_memory, e["title"])]
    assert len(new_events) == 3
    assert not any(e["title"] == "Already Seen AI Hackathon" for e in new_events)

    # 5. Stage 2 Dual Scoring (Simulated high-quality scoring)
    scored_events = []
    for ev in new_events:
        scored = dict(ev)
        if ev["source_type"] == "college_portal":
            # Student Opportunity Score (SOS) applied
            scored["learning_value"] = 8.5
            scored["skill_building"] = 8.0
            scored["network_value"] = 8.0
            scored["competitive_achievement"] = 7.5
            scored["career_relevance"] = 7.0
            scored["sos_score"] = 8.0
            scored["sos_verdict"] = "🔥"
            scored["fos_score"] = 5.0
            scored["fos_verdict"] = "⚠️"
            scored["recommendation"] = "APPLY"
        elif "Agent Challenge" in ev["title"]:
            # Global Founder Opportunity Score (FOS) applied
            scored["sponsor_quality"] = 9.5
            scored["hiring_potential"] = 9.0
            scored["startup_potential"] = 8.5
            scored["prize_score"] = 8.5
            scored["networking_potential"] = 8.0
            scored["fos_score"] = 9.0
            scored["fos_verdict"] = "🔥"
            scored["sos_score"] = 9.0
            scored["sos_verdict"] = "🔥"
            scored["recommendation"] = "APPLY IMMEDIATELY"
        else:
            # Low Quality Event
            scored["fos_score"] = 2.0
            scored["fos_verdict"] = "❌"
            scored["recommendation"] = "SKIP"
        scored_events.append(scored)

    # 6. Stage 3 Personalized Relevance Evaluation
    for ev in scored_events:
        if "Agent" in ev["title"]:
            ev["relevance_score"] = 9.8
            ev["relevance_explanation"] = "Direct match for your interest in autonomous agents."
        elif "CODELYMPICS" in ev["title"]:
            ev["relevance_score"] = 8.2
            ev["relevance_explanation"] = "Premier campus competitive coding event at VIT."
        else:
            ev["relevance_score"] = 2.0
            ev["relevance_explanation"] = "Low relevance quiz."

    # 7. Stage 4 Composite Ranking & Quality Gates
    passing_events = []
    for ev in scored_events:
        is_college = ev.get("source_type") == "college_portal"
        opp_score = ev.get("sos_score", 0.0) if is_college else ev.get("fos_score", 0.0)
        verdict = ev.get("sos_verdict") if is_college else ev.get("fos_verdict")
        rec = ev.get("recommendation", "CONSIDER")

        # Quality Gates:
        # College events: SOS >= 3.0 and verdict != '❌' and rec != 'SKIP'
        # Global events: FOS >= 5.0 and verdict != '❌' and rec != 'SKIP'
        passes = False
        if is_college:
            passes = (opp_score >= 3.0) and (verdict != "❌") and (rec != "SKIP")
        else:
            passes = (opp_score >= 5.0) and (verdict != "❌") and (rec != "SKIP")

        if passes:
            ev["composite_rank"] = calculate_composite_rank(ev)
            passing_events.append(ev)

    assert len(passing_events) == 2
    # Check that college event passed with SOS
    assert any(e["title"] == "VIT Chennai CODELYMPICS 2026" for e in passing_events)
    # Check that low quality event was filtered out
    assert not any(e["title"] == "Low Quality Spam Contest" for e in passing_events)

    # Check composite rank calculation
    passing_events.sort(key=lambda x: x.get("composite_rank", 0.0), reverse=True)
    top = passing_events[0]
    assert top["title"] == "Global Autonomous Agent Challenge"
    # blended: (9.8 * 0.5) + (9.0 * 0.3) + (5.0 * 0.2) = 8.6; urgency 2.0 * link 1.0 = 17.2
    assert top["composite_rank"] == 17.2

    # 8. Stage 5 Telegram Notification Generation
    text, markup = format_notification(passing_events, user_name=cfg.user_name)
    assert "Global Autonomous Agent Challenge" in text
    assert "VIT Chennai CODELYMPICS 2026" in text
    assert len(markup["inline_keyboard"]) == 2

    # 9. Persistence & Sync Verification
    for ev in scored_events:
        event_id = upsert_event(ev, db_path=db_path)
        save_event_score(event_id, user_id=1, score=ev, db_path=db_path)
        cleaned_memory = mark_seen(cleaned_memory, ev["title"], ev.get("link", ""), ev.get("source", ""), ev)

    # Verify records in SQLite
    with get_connection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT count(*) as count FROM events")
        assert cursor.fetchone()["count"] == 3

        cursor.execute("SELECT count(*) as count FROM event_scores WHERE verdict = '🔥'")
        assert cursor.fetchone()["count"] == 2

    # Verify JSON sync
    sync_sqlite_to_seen_events_json(db_path=db_path, json_path=memory_path)
    assert os.path.exists(memory_path)
    with open(memory_path, "r") as f:
        synced_data = json.load(f)
    assert len(synced_data) == 3
    assert any(v["title"] == "Global Autonomous Agent Challenge" for v in synced_data.values())


def test_main_cli_dry_run(test_env, monkeypatch):
    """Test full CLI main() function execution in dry-run mode."""
    from main import main

    test_args = ["main.py", "--dry-run", "--config", "config.yaml"]
    monkeypatch.setattr("sys.argv", test_args)

    mock_event = {
        "title": "Cli Test Autonomous Hackathon 2026",
        "event_type": "hackathon",
        "source": "devpost",
        "source_type": "global_platform",
        "link": "https://devpost.com/cli-test",
        "registration_deadline": "4 days left",
        "mode": "online",
        "prize_pool": "$20,000",
        "sponsors": ["Google", "DeepMind"],
        "description": "Agentic test event.",
        "tags": ["AI"],
    }

    mock_scored = dict(mock_event)
    mock_scored.update({
        "fos_score": 8.8,
        "fos_verdict": "🔥",
        "easy_winning_potential": 8.0,
        "recommendation": "APPLY",
        "why_relevant": "Top AI hackathon.",
        "relevance_score": 9.2,
        "relevance_explanation": "Direct match.",
    })

    with patch("main.fetch_devpost", return_value="--- SOURCE: DEVPOST ---\nTitle: Cli Test Autonomous Hackathon 2026"), \
         patch("main.fetch_devfolio", return_value=None), \
         patch("main.fetch_unstop", return_value=None), \
         patch("main.fetch_hackerearth", return_value=None), \
         patch("main.fetch_dorahacks", return_value=None), \
         patch("main.fetch_mlh", return_value=None), \
         patch("main.fetch_college_events", return_value=None), \
         patch("main.extract_events", return_value=[mock_event]), \
         patch("main.score_events", return_value=[mock_scored]), \
         patch("main.score_relevance", return_value=[mock_scored]), \
         patch("main.get_github_intel", return_value={}):

        exit_code = main()
        assert exit_code == 0
