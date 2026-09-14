"""Unit tests for repository and project status inspection."""

from src.git_status import get_git_info, get_project_metrics, get_project_status_summary


def test_get_git_info():
    """Verify git information extraction returns expected keys."""
    info = get_git_info()
    assert "branch" in info
    assert "commit_hash" in info
    assert "commit_msg" in info
    assert isinstance(info["is_clean"], bool)


def test_get_project_metrics():
    """Verify project database metrics extraction."""
    metrics = get_project_metrics()
    assert "total_events" in metrics
    assert "fire_events" in metrics
    assert "urgent_deadlines" in metrics
    assert isinstance(metrics["total_events"], int)


def test_get_project_status_summary():
    """Verify generated project status string."""
    summary = get_project_status_summary()
    assert isinstance(summary, str)
    assert len(summary) > 0
    assert "Repo active on" in summary
