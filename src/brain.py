"""
Brain — Gemini 2.5 Flash AI filtering and classification.

Analyzes scraped content from all three sources (Devpost, Devfolio, VIT EventHub)
and extracts ALL tech-related hackathons and workshops.
Also evaluates each match for portfolio standout potential.
"""

import json
import logging
import os

from google import genai
from google.genai import types
from pydantic import BaseModel

log = logging.getLogger(__name__)

# ── Pydantic schema for strict structured output ──

class Event(BaseModel):
    title: str
    event_type: str       # "hackathon" or "workshop"
    source: str           # "devpost", "devfolio", or "vit_eventhub"
    date: str | None
    link: str | None
    why_relevant: str     # Personalized pitch including portfolio evaluation


class EventList(BaseModel):
    events: list[Event]


# ── System instruction for Gemini ──

SYSTEM_INSTRUCTION = """You are an event scout for a computer science student. Your job is to extract ALL tech-related hackathons and workshops from the provided content.

**What to include**: Any hackathon or workshop related to technology, software, engineering, or computer science. This includes but is not limited to: AI/ML, web development, mobile apps, blockchain, cybersecurity, IoT, robotics, game development, data science, cloud computing, DevOps, open source, fintech, AR/VR, embedded systems, competitive programming, UI/UX design, and any other tech domain.

**What to exclude**: Non-tech events such as sports, cultural fests, literary events, music, dance, art exhibitions, debates, or business/MBA case competitions with no tech component.

You will receive text scraped from three sources: Devpost, Devfolio, and VIT EventHub. Search for BOTH hackathons AND workshops across ALL three sources — any source can have either type.

For each event found, classify it as "hackathon" or "workshop".

**Portfolio evaluation rule**: For each event, evaluate whether the resulting project would make a strong, standout addition to a unique personal portfolio website. Factor this into your `why_relevant` pitch — mention the portfolio impact (e.g., "Building this would showcase your X skills and stand out on a portfolio").

**Source identification**: Set the `source` field based on which section of the input the event came from:
- Content under "--- SOURCE: DEVPOST ---" → source = "devpost"
- Content under "--- SOURCE: DEVFOLIO ---" → source = "devfolio"
- Content under "--- SOURCE: VIT EVENTHUB ---" → source = "vit_eventhub"

**Link extraction**: Extract the registration/event URL if available. For Devpost events, links typically look like https://devpost.com/... For Devfolio, they look like https://[slug].devfolio.co. If no link is found, set it to null.

If no tech events are found at all, return an empty list."""

# Model configuration
MODEL_NAME = "gemini-2.5-flash"
TEMPERATURE = 0.1


def _get_client() -> genai.Client | None:
    """Initialize Gemini client from environment variable."""
    api_key = os.environ.get("GEMINI_API_KEY", "").strip()
    if not api_key:
        log.error("GEMINI_API_KEY environment variable is not set")
        return None

    try:
        client = genai.Client(api_key=api_key)
        return client
    except Exception as e:
        log.error(f"Failed to initialize Gemini client: {e}")
        return None


def _build_prompt(contents: dict[str, str]) -> str:
    """
    Combine scraped content from all sources into a single prompt.
    Uses clear delimiters so Gemini can identify which source each event came from.
    """
    sections = []

    source_labels = {
        "devpost": "DEVPOST",
        "devfolio": "DEVFOLIO",
        "vit_eventhub": "VIT EVENTHUB",
    }

    for key, label in source_labels.items():
        content = contents.get(key, "")
        if content:
            # If the content already has a source header, use as-is
            if f"--- SOURCE: {label}" in content:
                sections.append(content)
            else:
                sections.append(f"--- SOURCE: {label} ---\n{content}")

    if not sections:
        return ""

    return (
        "Analyze the following scraped content and extract relevant "
        "hackathons and workshops matching my interests.\n\n"
        + "\n\n".join(sections)
    )


def analyze_events(contents: dict[str, str]) -> list[dict]:
    """
    Send scraped content to Gemini for analysis and filtering.

    Args:
        contents: Dict mapping source names to their scraped text content.
                  Keys: "devpost", "devfolio", "vit_eventhub"

    Returns:
        List of event dicts matching the interest profile.
        Each dict has: title, event_type, source, date, link, why_relevant
    """
    client = _get_client()
    if not client:
        return []

    prompt = _build_prompt(contents)
    if not prompt:
        log.warning("No content to analyze — all fetchers returned empty")
        return []

    log.info(f"Sending {len(prompt)} chars to Gemini {MODEL_NAME} for analysis")

    try:
        response = client.models.generate_content(
            model=MODEL_NAME,
            contents=prompt,
            config=types.GenerateContentConfig(
                system_instruction=SYSTEM_INSTRUCTION,
                response_mime_type="application/json",
                response_schema=EventList,
                temperature=TEMPERATURE,
            ),
        )

        # Try automatic Pydantic parsing first
        try:
            parsed: EventList = response.parsed
            events = [event.model_dump() for event in parsed.events]
        except (AttributeError, Exception):
            # Fall back to manual JSON parsing
            raw_text = response.text
            data = json.loads(raw_text)
            events = data.get("events", data if isinstance(data, list) else [])

        log.info(f"Gemini found {len(events)} matching events")

        # Validate and clean up events
        cleaned = []
        for event in events:
            if isinstance(event, dict) and event.get("title"):
                cleaned.append({
                    "title": event.get("title", "Unknown"),
                    "event_type": event.get("event_type", "hackathon"),
                    "source": event.get("source", "unknown"),
                    "date": event.get("date"),
                    "link": event.get("link"),
                    "why_relevant": event.get("why_relevant", ""),
                })

        return cleaned

    except json.JSONDecodeError as e:
        log.error(f"Gemini response was not valid JSON: {e}")
        log.debug(f"Raw response: {response.text[:500] if response else 'None'}")
        return []
    except Exception as e:
        log.error(f"Gemini analysis failed: {e}")
        return []
