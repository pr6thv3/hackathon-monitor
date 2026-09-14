"""
Unit tests for Hackathon Monitor v4 Transformation optimizations.

Tests:
1. Enhanced composite ranking formula incorporating FOS/SOS & easy win probability.
2. Integrated user feedback loop modulating Stage 3 relevance scores.
3. CLI utility options (--stats, --feedback, --list-events).
"""

import os
import pytest
from unittest.mock import patch
from main import calculate_composite_rank, main
from src.feedback import FeedbackProcessor
from src.db import init_db, upsert_event, get_connection


@pytest.fixture
def temp_db(tmp_path):
    db_file = str(tmp_path / "opt_test.db")
    init_db(db_file)
    return db_file


def test_calculate_composite_rank_formula():
    """Verify that composite rank blends relevance, opp_score (FOS/SOS), easy win, urgency, and link penalty."""
    event = {
        "title": "AI Agent Buildathon",
        "relevance_score": 9.0,
        "fos_score": 8.0,
        "easy_winning_potential": 7.0,
        "registration_deadline": "3 days left",
        "link": "https://example.com/register",
        "source_type": "global_platform",
    }
    # blended = (9.0 * 0.5) + (8.0 * 0.3) + (7.0 * 0.2) = 4.5 + 2.4 + 1.4 = 8.3
    # urgency = 2.0 (<= 7 days)
    # link_penalty = 1.0
    # expected rank = 8.3 * 2.0 * 1.0 = 16.6
    rank = calculate_composite_rank(event)
    assert rank == 16.6

    # Test without link penalty (link is None)
    event_no_link = dict(event)
    event_no_link["link"] = None
    # expected rank = 8.3 * 2.0 * 0.7 = 11.62
    rank_no_link = calculate_composite_rank(event_no_link)
    assert rank_no_link == 11.62


def test_feedback_loop_relevance_adjustment(temp_db):
    """Verify that recording user feedback adjusts relevance scores via FeedbackProcessor."""
    fb = FeedbackProcessor(db_path=temp_db)

    # Insert mock event in DB via upsert_event
    mock_event = {
        "title": "VIT Hackathon 2026",
        "source": "vit_eventhub",
        "event_type": "hackathon",
        "tags": ["AI", "python"],
    }
    event_id = upsert_event(mock_event, db_path=temp_db)

    # Record 'applied' feedback for hackathons
    fb.record_feedback(user_id=1, event_id=event_id, action="applied")

    weights = fb.get_behavioral_weights(user_id=1)
    assert "hackathon" in weights["type_multipliers"]
    assert weights["type_multipliers"]["hackathon"] > 1.0

    # Adjust base relevance score of 8.0
    adjusted = fb.adjust_relevance(
        base_score=8.0,
        event_type="hackathon",
        tags=["AI"],
        weights=weights,
    )
    # Base 8.0 * 0.7 + 8.0 * 1.3 * 0.3 = 5.6 + 3.12 = 8.72 -> 8.7
    assert adjusted > 8.0


def test_cli_utility_flags(temp_db, monkeypatch, capsys):
    """Test main CLI --stats, --feedback, and --list-events options."""
    with patch("src.db.DEFAULT_DB_PATH", temp_db), \
         patch("src.feedback.DEFAULT_DB_PATH", temp_db):

        # Test --stats
        test_args = ["main.py", "--stats"]
        monkeypatch.setattr("sys.argv", test_args)
        exit_code = main()
        assert exit_code == 0
        captured = capsys.readouterr()
        assert "System Metrics" in captured.out

        # Test --feedback
        test_args_fb = ["main.py", "--feedback", "1", "applied"]
        monkeypatch.setattr("sys.argv", test_args_fb)
        exit_code_fb = main()
        assert exit_code_fb == 0
        captured_fb = capsys.readouterr()
        assert "Successfully recorded feedback" in captured_fb.out

        # Test --list-events
        test_args_list = ["main.py", "--list-events"]
        monkeypatch.setattr("sys.argv", test_args_list)
        exit_code_list = main()
        assert exit_code_list == 0
        captured_list = capsys.readouterr()
        assert "Recent Stored Opportunities" in captured_list.out
