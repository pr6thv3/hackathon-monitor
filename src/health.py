"""
Pipeline Health & Source Observability Tracker (v4).

Monitors:
- Consecutive source failures and circuit breaking
- Pipeline execution metrics (durations, counts, errors)
- High-signal run summaries for diagnosis and monitoring
"""

import json
import logging
import time
from dataclasses import dataclass, field
from typing import Any

log = logging.getLogger(__name__)


@dataclass
class RunMetrics:
    run_id: str
    start_time: float = field(default_factory=time.time)
    duration_seconds: float = 0.0
    sources_attempted: int = 0
    sources_succeeded: int = 0
    sources_failed: list[str] = field(default_factory=list)
    events_extracted: int = 0
    events_new: int = 0
    events_scored: int = 0
    null_links: int = 0
    notifications_sent: int = 0

    def finish(self) -> dict[str, Any]:
        self.duration_seconds = round(time.time() - self.start_time, 2)
        summary = {
            "run_id": self.run_id,
            "duration_seconds": self.duration_seconds,
            "sources_attempted": self.sources_attempted,
            "sources_succeeded": self.sources_succeeded,
            "sources_failed": self.sources_failed,
            "events_extracted": self.events_extracted,
            "events_new": self.events_new,
            "events_scored": self.events_scored,
            "null_links": self.null_links,
            "notifications_sent": self.notifications_sent,
        }
        log.info(f"📊 Pipeline Run Summary: {json.dumps(summary, indent=2)}")
        return summary


class SourceHealthTracker:
    """Tracks health and consecutive failures across data sources."""

    def __init__(self, failure_alert_threshold: int = 3, disable_threshold: int = 10):
        self.failures: dict[str, int] = {}
        self.failure_alert_threshold = failure_alert_threshold
        self.disable_threshold = disable_threshold

    def record_success(self, source: str) -> None:
        """Reset consecutive failures upon successful fetch."""
        self.failures[source] = 0

    def record_failure(self, source: str, error: Exception | str) -> None:
        """Increment failure count and log alerts if threshold is reached."""
        count = self.failures.get(source, 0) + 1
        self.failures[source] = count

        log.warning(f"⚠️ Source '{source}' failed ({count} consecutive failure(s)): {error}")

        if count == self.failure_alert_threshold:
            log.error(f"🚨 Source Alert: '{source}' has failed {count} times consecutively!")

        if count >= self.disable_threshold:
            log.error(f"🛑 Source Circuit Breaker: '{source}' has failed {count} times. Requires manual inspection.")

    def is_source_enabled(self, source: str) -> bool:
        """Check if source is below the disable threshold."""
        return self.failures.get(source, 0) < self.disable_threshold
