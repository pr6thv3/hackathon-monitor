"""
User Feedback Learning & Relevance Adaptation Module (v4).

Collects explicit and implicit engagement signals:
- 'applied': Strong positive (+0.3 type, +0.2 topic)
- 'opened' / 'bookmarked': Moderate positive (+0.1 type, +0.05 topic)
- 'dismissed': Negative (-0.2 type)

Modulates future AI relevance scores to personalize recommendations over time.
"""

import logging
from typing import Any
from src.db import get_connection, DEFAULT_DB_PATH

log = logging.getLogger(__name__)


class FeedbackProcessor:
    """Manages recording feedback and computing dynamic preference weights."""

    def __init__(self, db_path: str = DEFAULT_DB_PATH):
        self.db_path = db_path

    def record_feedback(self, user_id: int, event_id: int, action: str) -> None:
        """
        Record a user feedback action.
        Valid actions: 'applied', 'opened', 'bookmarked', 'dismissed'.
        """
        valid_actions = ("applied", "opened", "bookmarked", "dismissed")
        if action not in valid_actions:
            log.warning(f"Invalid feedback action '{action}' ignored")
            return

        with get_connection(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
            INSERT INTO feedback (user_id, event_id, action)
            VALUES (?, ?, ?);
            """, (user_id, event_id, action))
            conn.commit()

        log.info(f"Recorded feedback '{action}' for event {event_id} (user {user_id})")

    def get_behavioral_weights(self, user_id: int = 1) -> dict[str, Any]:
        """
        Aggregate user feedback history to compute behavioral multipliers
        for event types and technical topics.
        """
        type_multipliers: dict[str, float] = {}
        topic_multipliers: dict[str, float] = {}

        try:
            with get_connection(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("""
                SELECT f.action, e.event_type, e.tags
                FROM feedback f
                JOIN events e ON f.event_id = e.id
                WHERE f.user_id = ?
                ORDER BY f.timestamp DESC
                LIMIT 200;
                """, (user_id,))
                rows = cursor.fetchall()

            for r in rows:
                action = r["action"]
                etype = r["event_type"]

                # Weight delta
                delta = 0.0
                if action == "applied":
                    delta = 0.3
                elif action in ("opened", "bookmarked"):
                    delta = 0.1
                elif action == "dismissed":
                    delta = -0.2

                type_multipliers[etype] = type_multipliers.get(etype, 1.0) + delta

                # Topic multipliers
                raw_tags = r["tags"]
                if raw_tags:
                    try:
                        import json
                        tags_list = json.loads(raw_tags) if isinstance(raw_tags, str) else raw_tags
                        topic_delta = 0.2 if action == "applied" else (0.05 if action in ("opened", "bookmarked") else 0.0)
                        if isinstance(tags_list, list):
                            for tag in tags_list:
                                topic_multipliers[tag] = topic_multipliers.get(tag, 1.0) + topic_delta
                    except Exception:
                        pass

            # Clamp multipliers between 0.5 and 1.5
            for k in type_multipliers:
                type_multipliers[k] = max(0.5, min(1.5, type_multipliers[k]))
            for k in topic_multipliers:
                topic_multipliers[k] = max(0.5, min(1.5, topic_multipliers[k]))

        except Exception as e:
            log.warning(f"Could not compute feedback weights: {e}")

        return {
            "type_multipliers": type_multipliers,
            "topic_multipliers": topic_multipliers,
        }

    def adjust_relevance(
        self,
        base_score: float,
        event_type: str,
        tags: list[str] = None,
        weights: dict[str, Any] = None,
    ) -> float:
        """
        Adjust base AI relevance score using learned user feedback weights.
        """
        if not weights:
            return base_score

        type_weights = weights.get("type_multipliers", {})
        type_mult = type_weights.get(event_type, 1.0)

        # Blend base AI score (70%) with behavioral adjustment (30%)
        adjusted = (base_score * 0.7) + (base_score * type_mult * 0.3)
        return round(max(0.0, min(10.0, adjusted)), 1)
