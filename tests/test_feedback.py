"""Unit tests for feedback processing and dynamic weight adjustment."""

import pytest
from src.db import init_db, upsert_event, get_connection
from src.feedback import FeedbackProcessor


@pytest.fixture
def test_db_path(tmp_path):
    db_file = str(tmp_path / "feedback_test.db")
    init_db(db_file)
    return db_file


def test_feedback_recording_and_weights(test_db_path):
    """Verify recording feedback actions and calculating behavioral multipliers."""
    fp = FeedbackProcessor(db_path=test_db_path)

    # Note: init_db already creates a default user with id=1

    # Create dummy event
    event = {
        "title": "Autonomous AI Builder Hackathon",
        "event_type": "hackathon",
        "source": "devpost",
        "tags": ["AI", "Agents"],
    }
    event_id = upsert_event(event, db_path=test_db_path)

    # Record 'applied' action
    fp.record_feedback(user_id=1, event_id=event_id, action="applied")

    weights = fp.get_behavioral_weights(user_id=1)
    type_mult = weights.get("type_multipliers", {})
    topic_mult = weights.get("topic_multipliers", {})

    assert type_mult.get("hackathon") == pytest.approx(1.3, 0.01)
    assert topic_mult.get("AI") == pytest.approx(1.2, 0.01)
    assert topic_mult.get("Agents") == pytest.approx(1.2, 0.01)


def test_invalid_feedback_action_ignored(test_db_path):
    """Verify invalid action strings do not insert records."""
    fp = FeedbackProcessor(db_path=test_db_path)
    fp.record_feedback(user_id=1, event_id=999, action="spam_click")

    with get_connection(test_db_path) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) as count FROM feedback WHERE user_id = 1")
        assert cursor.fetchone()["count"] == 0
