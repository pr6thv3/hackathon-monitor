"""
Repository and Project Status Module.

Inspects local git repository status (branch, recent commits, cleanliness)
and database metrics to provide authentic, high-signal project check-in context.
"""

import os
import subprocess
import logging
from typing import Any

from src.db import get_connection

log = logging.getLogger(__name__)


def get_git_info() -> dict[str, str]:
    """Retrieve current branch, latest commit hash, and commit subject."""
    info = {
        "branch": "main",
        "commit_hash": "main",
        "commit_msg": "",
        "is_clean": True,
    }

    try:
        branch = subprocess.check_output(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            stderr=subprocess.DEVNULL,
            text=True,
        ).strip()
        if branch:
            info["branch"] = branch
    except Exception:
        pass

    try:
        commit = subprocess.check_output(
            ["git", "log", "-1", "--format=%h %s (%cr)"],
            stderr=subprocess.DEVNULL,
            text=True,
        ).strip()
        if commit:
            parts = commit.split(" ", 1)
            info["commit_hash"] = parts[0]
            info["commit_msg"] = parts[1] if len(parts) > 1 else ""
    except Exception:
        pass

    try:
        status = subprocess.check_output(
            ["git", "status", "--porcelain"],
            stderr=subprocess.DEVNULL,
            text=True,
        ).strip()
        info["is_clean"] = len(status) == 0
    except Exception:
        pass

    return info


def get_project_metrics() -> dict[str, Any]:
    """Fetch database metrics: total events, top opportunities, and urgent deadlines."""
    metrics = {
        "total_events": 0,
        "fire_events": 0,
        "urgent_deadlines": 0,
    }

    try:
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT count(*) as total FROM events;")
            metrics["total_events"] = cursor.fetchone()["total"]

            cursor.execute("SELECT count(*) as total FROM event_scores WHERE verdict = '🔥';")
            metrics["fire_events"] = cursor.fetchone()["total"]

            cursor.execute("""
                SELECT count(*) as total FROM events
                WHERE registration_deadline LIKE '%1 day%'
                   OR registration_deadline LIKE '%2 day%'
                   OR registration_deadline LIKE '%3 day%'
                   OR registration_deadline LIKE '%4 day%'
                   OR registration_deadline LIKE '%5 day%'
                   OR registration_deadline LIKE '%6 day%'
                   OR registration_deadline LIKE '%7 day%';
            """)
            metrics["urgent_deadlines"] = cursor.fetchone()["total"]
    except Exception as err:
        log.warning(f"Could not read database metrics: {err}")

    return metrics


def get_project_status_summary() -> str:
    """
    Format a concise, natural 1-2 line status update about the repository
    and active tracking database.
    """
    git_info = get_git_info()
    metrics = get_project_metrics()

    commit_hash = git_info.get("commit_hash", "main")
    branch = git_info.get("branch", "main")
    total = metrics.get("total_events", 0)
    urgent = metrics.get("urgent_deadlines", 0)

    status_parts = [f"Repo active on <code>{branch}</code> (<code>{commit_hash}</code>)"]
    if total > 0:
        status_parts.append(f"{total} tracked opportunities")
    if urgent > 0:
        status_parts.append(f"<b>{urgent} closing this week</b>")

    return " · ".join(status_parts)
