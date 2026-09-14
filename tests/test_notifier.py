"""Unit tests for Telegram notification formatting, urgency tiers, and anti-fatigue limits."""

from src.notifier import format_notification, _parse_days_left, _get_urgency_tier, MAX_ITEMS_PER_MESSAGE


def test_parse_days_left():
    """Verify parsing days left from strings."""
    assert _parse_days_left("7 days left") == 7
    assert _parse_days_left("1 day left") == 1
    assert _parse_days_left("30 days left") == 30
    assert _parse_days_left(None) is None


def test_urgency_tiers():
    """Verify emoji assignment for deadline proximity."""
    assert _get_urgency_tier(5)[0] == "⚡"
    assert _get_urgency_tier(15)[0] == "🔥"
    assert _get_urgency_tier(45)[0] == "📌"
    assert _get_urgency_tier(None)[0] == "📌"


def test_format_notification_max_items():
    """Verify anti-fatigue rule: at most 3 items formatted per message."""
    five_events = [
        {
            "title": f"Event {i}",
            "event_type": "hackathon",
            "source": "devpost",
            "link": f"https://devpost.com/{i}",
            "registration_deadline": f"{i} days left",
            "relevance_score": 8.0,
            "relevance_explanation": "Test explanation."
        }
        for i in range(1, 6)
    ]

    text, markup = format_notification(five_events, user_name="TestUser")
    buttons = markup.get("inline_keyboard", [])
    assert len(buttons) == MAX_ITEMS_PER_MESSAGE
    assert len(buttons) <= 3
    assert "Event 1" in text
    assert "Event 3" in text
    assert "Event 4" not in text


def test_null_link_warning_present():
    """Verify explicit warning when an event has a null link."""
    event_no_link = [{
        "title": "Local College Makeathon",
        "event_type": "hackathon",
        "source": "vit_eventhub",
        "link": None,
        "registration_deadline": "5 days left",
        "relevance_score": 8.0,
        "relevance_explanation": "Hands-on buildathon."
    }]

    text, markup = format_notification(event_no_link, user_name="TestUser")
    assert "⚠️ <i>Direct URL unavailable — search" in text
    assert len(markup.get("inline_keyboard", [])) == 0
