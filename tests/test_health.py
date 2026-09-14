"""Unit tests for pipeline health tracking and run metrics."""

from src.health import RunMetrics, SourceHealthTracker


def test_run_metrics_finish():
    """Verify metrics calculation and summary output."""
    metrics = RunMetrics(run_id="test-run-1")
    metrics.sources_attempted = 5
    metrics.sources_succeeded = 4
    metrics.sources_failed = ["broken_source"]
    metrics.events_extracted = 12
    metrics.events_new = 8
    metrics.events_scored = 8
    metrics.notifications_sent = 3

    summary = metrics.finish()
    assert summary["run_id"] == "test-run-1"
    assert summary["sources_attempted"] == 5
    assert summary["sources_succeeded"] == 4
    assert summary["sources_failed"] == ["broken_source"]
    assert summary["events_extracted"] == 12
    assert summary["duration_seconds"] >= 0.0


def test_source_health_tracker():
    """Verify failure counting, threshold alerts, and reset on success."""
    tracker = SourceHealthTracker(failure_alert_threshold=3, disable_threshold=5)

    tracker.record_failure("devpost", "Timeout")
    assert tracker.failures.get("devpost") == 1
    assert tracker.is_source_enabled("devpost")

    tracker.record_failure("devpost", "HTTP 500")
    tracker.record_failure("devpost", "HTTP 502")
    assert tracker.failures.get("devpost") == 3
    assert tracker.is_source_enabled("devpost")

    tracker.record_failure("devpost", "HTTP 504")
    tracker.record_failure("devpost", "HTTP 503")
    # Now reached disable_threshold (5)
    assert not tracker.is_source_enabled("devpost")

    # Record success resets failure count
    tracker.record_success("devpost")
    assert tracker.failures.get("devpost") == 0
    assert tracker.is_source_enabled("devpost")
