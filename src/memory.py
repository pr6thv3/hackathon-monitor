"""
Memory System — Deduplication via JSON file with TTL-based pruning.

Tracks previously seen events using SHA-256 title hashing
to prevent duplicate notifications across runs, while expiring
stale records after 90 days to prevent unbounded memory growth.
"""

import hashlib
import json
import logging
import os
import re
from datetime import datetime, timezone, timedelta

log = logging.getLogger(__name__)

DEFAULT_MEMORY_PATH = "seen_events.json"
DEFAULT_TTL_DAYS = 90


def _normalize_title(title: str) -> str:
    """Normalize a title for consistent hashing: lowercase, strip, collapse whitespace."""
    title = title.lower().strip()
    title = re.sub(r"\s+", " ", title)
    return title


def _hash_title(title: str) -> str:
    """Generate SHA-256 hash of normalized title."""
    normalized = _normalize_title(title)
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def clean_expired_events(memory: dict, ttl_days: int = DEFAULT_TTL_DAYS) -> tuple[dict, int]:
    """
    Remove events older than TTL from memory.

    Returns:
        tuple of (cleaned_memory_dict, num_removed)
    """
    cutoff = datetime.now(timezone.utc) - timedelta(days=ttl_days)
    cleaned = {}
    removed = 0

    for key, entry in memory.items():
        date_str = entry.get("date_first_seen")
        if not date_str:
            # If no date, retain to prevent re-alerting immediately
            cleaned[key] = entry
            continue

        try:
            # Parse ISO format datetime
            # Handle trailing 'Z' if present
            if date_str.endswith("Z"):
                date_str = date_str[:-1] + "+00:00"
            first_seen = datetime.fromisoformat(date_str)
            if first_seen.tzinfo is None:
                first_seen = first_seen.replace(tzinfo=timezone.utc)

            if first_seen > cutoff:
                cleaned[key] = entry
            else:
                removed += 1
        except Exception:
            # In case of malformed date string, keep the record safely
            cleaned[key] = entry

    if removed > 0:
        log.info(f"TTL Pruning: Removed {removed} events older than {ttl_days} days from memory")

    return cleaned, removed


def load_memory(path: str = DEFAULT_MEMORY_PATH, auto_clean: bool = True, ttl_days: int = DEFAULT_TTL_DAYS) -> dict:
    """
    Load the memory file from disk with optional TTL expiry pruning.
    Returns an empty dict if the file doesn't exist (first run).
    """
    if not os.path.exists(path):
        log.info(f"Memory file '{path}' not found — starting fresh")
        return {}

    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        log.info(f"Loaded {len(data)} seen events from memory")

        if auto_clean:
            cleaned, removed = clean_expired_events(data, ttl_days=ttl_days)
            if removed > 0:
                save_memory(cleaned, path=path)
                return cleaned

        return data
    except (json.JSONDecodeError, IOError) as e:
        log.error(f"Failed to load memory file: {e} — starting fresh")
        return {}


def save_memory(memory: dict, path: str = DEFAULT_MEMORY_PATH) -> None:
    """
    Save memory to disk with atomic write (write to .tmp, then rename).
    Prevents corruption if the process is interrupted mid-write.
    """
    tmp_path = path + ".tmp"
    try:
        with open(tmp_path, "w", encoding="utf-8") as f:
            json.dump(memory, f, indent=2, ensure_ascii=False)
        # Atomic rename
        os.replace(tmp_path, path)
        log.info(f"Saved {len(memory)} events to memory ({path})")
    except IOError as e:
        log.error(f"Failed to save memory: {e}")
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
            "sos_score": details.get("sos_score"),
            "easy_winning_potential": details.get("easy_winning_potential"),
            "fos_verdict": details.get("fos_verdict"),
            "sos_verdict": details.get("sos_verdict"),
            "relevance_score": details.get("relevance_score"),
            "event_type": details.get("event_type"),
            "source_type": details.get("source_type"),
            "mode": details.get("mode"),
            "registration_deadline": details.get("registration_deadline"),
            "dates": details.get("dates"),
            "team_size": details.get("team_size"),
            "why_relevant": details.get("why_relevant"),
        })
    memory[title_hash] = entry
    log.debug(f"Marked as seen: '{title}' from {source}")
    return memory
