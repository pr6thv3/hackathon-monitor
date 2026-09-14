"""
Configuration & User Preference Module (v4).

Loads user settings from config.yaml and parses natural language preference
statements into structured PreferenceProfile objects via Gemini, cached locally
to minimize LLM quota consumption.
"""

import hashlib
import json
import logging
import os
import yaml
from typing import Any
from pydantic import BaseModel, Field
from google import genai
from google.genai import types

log = logging.getLogger(__name__)

CONFIG_PATH = "config.yaml"
CACHE_PATH = "preference_cache.json"


class PortalConfig(BaseModel):
    id: str
    name: str
    url: str
    adapter: str = "vit_eventhub"
    auth: dict[str, Any] = Field(default_factory=dict)


class NotificationConfig(BaseModel):
    channel: str = "telegram"
    max_per_run: int = 3
    digest_mode: bool = True
    urgency_tiers: dict[str, int] = Field(
        default_factory=lambda: {
            "immediate_days": 7,
            "daily_digest_days": 30,
            "weekly_digest_days": 90,
        }
    )


class PreferenceProfile(BaseModel):
    raw_text: str = ""
    topics: list[str] = Field(default_factory=list)
    wanted_event_types: list[str] = Field(default_factory=list)
    excluded_event_types: list[str] = Field(default_factory=list)
    online_preference: str = "either"  # "online", "offline", "either"
    skill_level: str = "intermediate"
    primary_goal: str = "mixed"  # "learning", "career", "competition", "networking", "mixed"
    implicit_interests: list[str] = Field(default_factory=list)


class AppConfig(BaseModel):
    user_name: str = "Builder"
    portals: list[PortalConfig] = Field(default_factory=list)
    raw_preferences: str = ""
    preference_profile: PreferenceProfile = Field(default_factory=PreferenceProfile)
    notifications: NotificationConfig = Field(default_factory=NotificationConfig)


def _hash_text(text: str) -> str:
    """Generate SHA-256 hash for preference caching."""
    return hashlib.sha256(text.strip().encode("utf-8")).hexdigest()


def _parse_nl_preferences_with_llm(raw_text: str) -> PreferenceProfile:
    """
    Parse a natural language interest statement into a structured PreferenceProfile
    using Groq or Gemini.
    """
    groq_key = os.environ.get("GROQ_API_KEY", "").strip()
    gemini_key = os.environ.get("GEMINI_API_KEY", "").strip()

    if not groq_key and not gemini_key:
        log.warning("Neither GROQ_API_KEY nor GEMINI_API_KEY found — using rule-based preference profile defaults")
        return PreferenceProfile(
            raw_text=raw_text,
            topics=["AI", "ML", "robotics", "web3", "competitive-programming", "software-engineering"],
            wanted_event_types=["hackathon", "competition", "workshop", "buildathon"],
            excluded_event_types=["seminar", "conference"],
            online_preference="either",
            primary_goal="competition",
        )

    instruction = """You are a student preference extraction specialist.
Parse the user's natural language interest statement into a structured JSON profile.
Extract:
- topics: specific technology areas (e.g. ['AI', 'agents', 'robotics', 'systems'])
- wanted_event_types: from ['hackathon', 'competition', 'workshop', 'bootcamp', 'buildathon', 'hiring_challenge', 'open_source']
- excluded_event_types: e.g. ['seminar', 'conference']
- online_preference: 'online', 'offline', or 'either'
- primary_goal: 'learning', 'career', 'competition', 'networking', or 'mixed'
- implicit_interests: inferred keywords (e.g. ['project-building', 'portfolio'])"""

    prompt = f"Student statement:\n\"{raw_text}\""

    # Attempt Groq first if key present
    if groq_key:
        try:
            from groq import Groq
            client = Groq(api_key=groq_key)
            full_prompt = (
                f"{instruction}\n\n"
                f"You MUST respond ONLY with a valid JSON object matching this schema:\n"
                f"{json.dumps(PreferenceProfile.model_json_schema(), indent=2)}\n\n"
                f"{prompt}"
            )
            completion = client.chat.completions.create(
                messages=[
                    {"role": "system", "content": "You are a precise JSON-emitting AI assistant."},
                    {"role": "user", "content": full_prompt},
                ],
                model="openai/gpt-oss-120b",
                response_format={"type": "json_object"},
                temperature=0.1,
            )
            data = json.loads(completion.choices[0].message.content)
            data["raw_text"] = raw_text
            return PreferenceProfile(**data)
        except Exception as e:
            log.warning(f"Failed to parse preferences with Groq: {e}. Falling back to Gemini...")

    # Fallback / Direct Gemini
    if gemini_key:
        try:
            client = genai.Client(api_key=gemini_key)
            response = client.models.generate_content(
                model="gemini-2.5-flash",
                contents=prompt,
                config=types.GenerateContentConfig(
                    system_instruction=instruction,
                    response_mime_type="application/json",
                    response_schema=PreferenceProfile,
                    temperature=0.1,
                ),
            )
            try:
                profile: PreferenceProfile = response.parsed
                profile.raw_text = raw_text
                return profile
            except Exception:
                data = json.loads(response.text)
                data["raw_text"] = raw_text
                return PreferenceProfile(**data)
        except Exception as e:
            log.error(f"Failed to parse preferences with Gemini: {e}")

    return PreferenceProfile(
        raw_text=raw_text,
        topics=["AI", "ML", "systems", "hackathons"],
        wanted_event_types=["hackathon", "competition"],
        excluded_event_types=["seminar"],
        online_preference="either",
    )


def resolve_preference_profile(raw_text: str) -> PreferenceProfile:
    """
    Resolve PreferenceProfile from cache if unmodified; otherwise query Gemini.
    """
    if not raw_text.strip():
        return PreferenceProfile()

    text_hash = _hash_text(raw_text)

    # Check cache
    if os.path.exists(CACHE_PATH):
        try:
            with open(CACHE_PATH, "r", encoding="utf-8") as f:
                cached = json.load(f)
            if cached.get("hash") == text_hash and "profile" in cached:
                log.info("Loaded structured preference profile from cache")
                return PreferenceProfile(**cached["profile"])
        except Exception as e:
            log.warning(f"Failed to read preference cache: {e}")

    log.info("Resolving new/updated preferences with LLM (Groq/Gemini)...")
    profile = _parse_nl_preferences_with_llm(raw_text)

    # Save to cache
    try:
        with open(CACHE_PATH, "w", encoding="utf-8") as f:
            json.dump({"hash": text_hash, "profile": profile.model_dump()}, f, indent=2)
        log.info(f"Cached structured preference profile to {CACHE_PATH}")
    except Exception as e:
        log.warning(f"Could not write preference cache: {e}")

    return profile


def load_config(config_path: str = CONFIG_PATH) -> AppConfig:
    """
    Load and parse configuration file.
    Falls back gracefully to sensible defaults if missing.
    """
    if not os.path.exists(config_path):
        log.warning(f"Config file '{config_path}' not found — using default configuration")
        return AppConfig()

    try:
        with open(config_path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}

        user_data = data.get("user", {})
        user_name = user_data.get("name", "Builder") if isinstance(user_data, dict) else "Builder"

        portals = []
        for p in data.get("portals", []):
            if isinstance(p, dict):
                portals.append(PortalConfig(**p))

        raw_prefs = data.get("preferences", "").strip()
        pref_profile = resolve_preference_profile(raw_prefs)

        notif_data = data.get("notifications", {})
        notifications = NotificationConfig(**notif_data) if isinstance(notif_data, dict) else NotificationConfig()

        return AppConfig(
            user_name=user_name,
            portals=portals,
            raw_preferences=raw_prefs,
            preference_profile=pref_profile,
            notifications=notifications,
        )
    except Exception as e:
        log.error(f"Failed to load '{config_path}': {e} — using defaults")
        return AppConfig()
