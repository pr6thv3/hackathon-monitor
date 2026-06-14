"""
Memory System — Deduplication via JSON file.

Tracks previously seen events using SHA-256 title hashing
to prevent duplicate WhatsApp notifications across runs.
"""

import hashlib
import json
import logging
import os
import re
from datetime import datetime, timezone

log = logging.getLogger(__name__)


def _normalize_title(title: str) -> str:
    """Normalize a title for consistent hashing: lowercase, strip, collapse whitespace."""
    title = title.lower().strip()
    title = re.sub(r"\s+", " ", title)
    return title


def _hash_title(title: str) -> str:
    """Generate SHA-256 hash of normalized title."""
    normalized = _normalize_title(title)
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def load_memory(path: str = "seen_events.json") -> dict:
    """
    Load the memory file from disk.
    Returns an empty dict if the file doesn't exist (first run).
    """
    if not os.path.exists(path):
        log.info(f"Memory file '{path}' not found — starting fresh")
        return {}

    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        log.info(f"Loaded {len(data)} seen events from memory")
        return data
    except (json.JSONDecodeError, IOError) as e:
        log.error(f"Failed to load memory file: {e} — starting fresh")
        return {}


def save_memory(memory: dict, path: str = "seen_events.json") -> None:
    """
    Save memory to disk with atomic write (write to .tmp, then rename).
    Prevents corruption if the process is interrupted mid-write.
    """
    tmp_path = path + ".tmp"
    try:
        with open(tmp_path, "w", encoding="utf-8") as f:
            json.dump(memory, f, indent=2, ensure_ascii=False)
        # Atomic rename (on most filesystems)
        os.replace(tmp_path, path)
        log.info(f"Saved {len(memory)} events to memory")
    except IOError as e:
        log.error(f"Failed to save memory: {e}")
        # Clean up tmp file if it exists
        if os.path.exists(tmp_path):
            os.remove(tmp_path)
        raise


def is_new(memory: dict, title: str) -> bool:
    """Check if an event title has NOT been seen before."""
    title_hash = _hash_title(title)
    return title_hash not in memory


def mark_seen(memory: dict, title: str, link: str, source: str, details: dict = None) -> dict:
    """
    Mark an event as seen by adding it to memory with optional scored details.
    Returns the updated memory dict.
    """
    title_hash = _hash_title(title)
    entry = {
        "title": title,
        "link": link,
        "source": source,
        "date_first_seen": datetime.now(timezone.utc).isoformat(),
    }
    if details:
        entry.update({
            "fos_score": details.get("fos_score"),
            "easy_winning_potential": details.get("easy_winning_potential"),
            "fos_verdict": details.get("fos_verdict"),
            "mode": details.get("mode"),
            "registration_deadline": details.get("registration_deadline"),
            "dates": details.get("dates"),
            "team_size": details.get("team_size"),
            "why_relevant": details.get("why_relevant"),
        })
    memory[title_hash] = entry
    log.debug(f"Marked as seen: '{title}' from {source}")
    return memory
