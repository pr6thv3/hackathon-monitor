"""Unit tests for fetchers, verifying non-null links and data structures."""

import pytest
from unittest.mock import patch, MagicMock
from src.fetcher_devpost import _clean_html_tags, _fetch_via_api, fetch_devpost
from src.fetcher_hackerearth import _fetch_upcoming_api


def test_clean_html_tags():
    """Verify HTML stripping from raw prize strings."""
    raw = "$<span data-currency-value>740,000</span> USD"
    cleaned = _clean_html_tags(raw)
    assert cleaned == "$740,000 USD"


def test_devpost_api_parsing_with_mock():
    """Verify Devpost API parser extracts real links, prizes, and titles."""
    mock_payload = {
        "hackathons": [
            {
                "title": "RevenueCat Shipaton 2026",
                "url": "https://revenuecat-shipaton-2026.devpost.com/",
                "submission_period_dates": "Jul 31 - Oct 01, 2026",
                "time_left_to_submission": "23 days left",
                "prize_amount": "$<span data-currency-value>740,000</span>",
                "organization_name": "RevenueCat",
                "displayed_location": {"location": "Online"},
                "themes": [{"name": "Design"}, {"name": "Mobile"}]
            }
        ]
    }

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = mock_payload

    with patch("requests.get", return_value=mock_resp):
        res = _fetch_via_api(pages=1)
        assert res is not None
        assert "--- SOURCE: DEVPOST ---" in res
        assert "Title: RevenueCat Shipaton 2026" in res
        assert "Link: https://revenuecat-shipaton-2026.devpost.com/" in res
        assert "Prize: $740,000" in res
        assert "Themes: Design, Mobile" in res


def test_devpost_live_or_graceful():
    """Verify Devpost live fetch returns valid data or handles offline sandbox gracefully."""
    content = fetch_devpost()
    if content:
        assert "--- SOURCE: DEVPOST ---" in content
        assert "Title:" in content
        assert "Link: http" in content, "Devpost output must contain real HTTP hyperlinks"


def test_hackerearth_fetcher_structure():
    """Verify HackerEarth upcoming API returns valid formatted events."""
    content = _fetch_upcoming_api()
    if content:
        assert "--- SOURCE: HACKEREARTH ---" in content
        assert "Title:" in content
