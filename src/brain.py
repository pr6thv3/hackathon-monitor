"""
Brain Module — Two-stage Gemini 2.5 Flash AI pipeline.

Stage 1: Extract all tech hackathons and workshops from raw scraped text sources.
Stage 2: Score events with GitHub context, evaluating:
  - Founder Opportunity Score (FOS)
  - Easy-Win Potential (win probability, niche audiences, prize tracks)
  - Quality filter: keeps events if FOS >= 7.0 OR Easy-Win >= 7.0.
"""

import json
import logging
import os
from google import genai
from google.genai import types
from pydantic import BaseModel, Field

log = logging.getLogger(__name__)

MODEL_NAME = "gemini-2.5-flash"
TEMPERATURE = 0.1

# ────────────────────────────────────────────────────────────────────────
# STAGE 1: EXTRACTION PYDANTIC SCHEMA
# ────────────────────────────────────────────────────────────────────────

class ExtractedEvent(BaseModel):
    title: str = Field(description="The name of the hackathon or workshop.")
    event_type: str = Field(description="Type of the event: 'hackathon' or 'workshop'.")
    source: str = Field(description="Source platform: 'devpost', 'devfolio', 'unstop', 'hackerearth', 'dorahacks', 'mlh', or 'vit_eventhub'.")
    dates: str | None = Field(None, description="Event dates or timeline.")
    registration_deadline: str | None = Field(None, description="Registration deadline or end date.")
    link: str | None = Field(None, description="Registration/event page link.")
    mode: str | None = Field(None, description="Event mode: 'online', 'offline', or 'hybrid'.")
    team_size: str | None = Field(None, description="Team size rules (e.g. '1-4 players').")
    prize_pool: str | None = Field(None, description="Total prize pool value or details.")
    sponsors: list[str] = Field(default_factory=list, description="List of sponsors, partners, or companies involved.")
    description: str | None = Field(None, description="Short summary/tagline of the event.")


class ExtractionResult(BaseModel):
    events: list[ExtractedEvent] = Field(description="List of extracted events.")


# ────────────────────────────────────────────────────────────────────────
# STAGE 2: SCORING & EVALUATION PYDANTIC SCHEMA
# ────────────────────────────────────────────────────────────────────────

class ScoredEvent(BaseModel):
    title: str
    event_type: str
    source: str
    dates: str | None
    registration_deadline: str | None
    link: str | None
    mode: str | None
    team_size: str | None
    
    # Prizes & Sponsors
    prize_pool: str | None
    prize_breakdown: str | None = Field(None, description="Details of how prizes are split/tracks.")
    sponsors: list[str]
    sponsor_analysis: str = Field(description="Why sponsors matter, hiring tracks, dev tools, or funding.")
    
    # FOS Components (1.0 to 10.0 scale)
    sponsor_quality: float = Field(description="Sponsor reputation score (1.0-10.0).")
    hiring_potential: float = Field(description="Recruitment, jobs, or interview loops (1.0-10.0).")
    startup_potential: float = Field(description="Accelerators, VC judges, pilot grants (1.0-10.0).")
    prize_score: float = Field(description="Prize pool attractiveness (1.0-10.0).")
    networking_potential: float = Field(description="Mentors, judges, offline summits (1.0-10.0).")
    
    # Easy-Win Evaluation (1.0 to 10.0 scale)
    easy_winning_potential: float = Field(description="Win probability score. Higher means lower competition, niche audiences, or many prize categories (1.0-10.0).")
    easy_winning_analysis: str = Field(description="Detailed reason for the easy-win potential (e.g. local college hackathon, numerous sponsor api prizes, smaller platform).")
    
    # Final FOS Scores
    fos_score: float = Field(description="Weighted FOS score out of 10 (30% Sponsor, 25% Hiring, 20% Startup, 15% Prize, 10% Networking).")
    fos_verdict: str = Field(description="Emoji verdict: 🔥 (FOS >= 8.5), ✅ (FOS >= 7.0), ⚠️ (FOS >= 5.0), ❌ (Skip).")
    
    # Written Analysis
    networking_analysis: str
    career_upside: str
    competition_analysis: str
    best_categories: list[str] = Field(description="Top 3 recommended categories/ideas to build (e.g. ['AI Agent workflow', 'Bounty project']).")
    roi_analysis: str = Field(description="ROI estimate (Prize+Upside vs Effort).")
    recommendation: str = Field(description="Final action: 'APPLY IMMEDIATELY', 'APPLY', 'ONLY IF FREE', or 'SKIP'.")
    why_relevant: str = Field(description="Personalized builder pitch summarizing why they should care.")


class ScoringResult(BaseModel):
    events: list[ScoredEvent] = Field(description="List of scored events.")


# ────────────────────────────────────────────────────────────────────────
# SYSTEM INSTRUCTIONS
# ────────────────────────────────────────────────────────────────────────

STAGE_1_INSTRUCTION = """You are an expert Hackathon Opportunity Scout.
Your job is to parse raw scraped text and extract ALL software/hardware tech-related hackathons and workshops.

Rules:
1. Include tech events: AI/ML, web dev, mobile, blockchain/web3, security, cloud, IoT, open-source, robotics, UI/UX, or developer tools.
2. Exclude purely cultural, sports, non-tech business, or literary events.
3. Keep college events if they are hackathons (e.g., student hackathons, offline college hackathons). Exclude simple college workshops/seminars unless they are hands-on, high-quality dev workshops.
4. Correctly identify the source based on the header delimiter in the text (e.g. '--- SOURCE: DEVPOST ---' is devpost, '--- SOURCE: VIT EVENTHUB ---' is vit_eventhub).
5. Extract links, team size, sponsors, and dates as accurately as possible. If no link is available, set it to null.
6. Return an empty list if no tech events are found. Do not invent events."""


STAGE_2_INSTRUCTION = """You are an elite Hackathon Opportunity Intelligence Agent and Founder Opportunity Scoring (FOS) evaluator.
Your goal is to evaluate, score, and analyze the list of extracted events using the provided GitHub Intelligence data.

For each event, compute two key scores on a 1.0 to 10.0 scale:

1. Founder Opportunity Score (FOS) - Weighted average:
   - Sponsor Quality (30% weight): Reputable tech firms (AWS, OpenAI, Solana, Vercel) = 9-10; mid-tier = 7-8; local/unknown = 1-5.
   - Hiring Potential (25% weight): Job boards, recruiting booths, resume reviews, fast-track interview loops = 8-10.
   - Startup Potential (20% weight): VC judges, accelerator passes, pilot programs, equity-free grants = 8-10.
   - Prize Score (15% weight): High cash prize pools or solid dev bounties = 8-10.
   - Networking Potential (10% weight): Profile of mentors, judges, high-profile offline venues = 8-10.

2. Easy-Win Potential (Win Probability):
   - Evaluate how likely a team is to win a prize.
   - Give HIGHER scores (8.0 - 10.0) if the event is:
     - Niche/Local/College: College hackathons or local offline hackathons have significantly less competition than global online hackathons.
     - Multi-prize: High number of prize tracks, sponsor API bounties, or runner-up awards.
     - Emerging Platforms/Communities: Smaller or less crowded platforms.
     - Beginner-friendly: Low complexity barrier.
   - Give LOWER scores (1.0 - 5.0) if the event is a massive, highly competitive global virtual hackathon (e.g. 5,000+ developers, only 3 top prizes).
   - Write a detailed 'easy_winning_analysis' explaining why it's easy or hard to place (e.g., 'With 15 sponsor tracks and only 200 expected participants, this offline college event has a massive win probability').

Combine the scores to determine the final FOS score and emoji verdict:
- FOS >= 8.5: 🔥
- FOS >= 7.0: ✅
- FOS >= 5.0: ⚠️
- FOS < 5.0: ❌

Inject details from the GitHub Intelligence data (repos, open issues, bounties, stars) into your evaluations and written analyses. Include actionable 'best_categories' for builders.
Return the structured scoring results."""


# ────────────────────────────────────────────────────────────────────────
# CLIENT & PIPELINE LOGIC
# ────────────────────────────────────────────────────────────────────────

def _get_client() -> genai.Client | None:
    """Initialize Gemini client from environment variable."""
    api_key = os.environ.get("GEMINI_API_KEY", "").strip()
    if not api_key:
        log.error("GEMINI_API_KEY environment variable is not set")
        return None
    try:
        return genai.Client(api_key=api_key)
    except Exception as e:
        log.error(f"Failed to initialize Gemini client: {e}")
        return None


def extract_events(contents: dict[str, str]) -> list[dict]:
    """
    Stage 1: Extract tech events from scraped raw contents.
    """
    client = _get_client()
    if not client:
        return []

    sections = []
    for key, text in contents.items():
        if text and len(text.strip()) > 50:
            sections.append(text)

    if not sections:
        log.warning("No scraped content to parse in Stage 1 extraction")
        return []

    prompt = "Scraped data sources:\n\n" + "\n\n".join(sections)
    log.info(f"Stage 1: Sending {len(prompt)} chars to Gemini for extraction...")

    try:
        response = client.models.generate_content(
            model=MODEL_NAME,
            contents=prompt,
            config=types.GenerateContentConfig(
                system_instruction=STAGE_1_INSTRUCTION,
                response_mime_type="application/json",
                response_schema=ExtractionResult,
                temperature=TEMPERATURE,
            ),
        )

        try:
            parsed: ExtractionResult = response.parsed
            events = [e.model_dump() for e in parsed.events]
        except (AttributeError, Exception):
            data = json.loads(response.text)
            events = data.get("events", data if isinstance(data, list) else [])

        log.info(f"Stage 1: Extracted {len(events)} events from raw data")
        return events

    except Exception as e:
        log.error(f"Stage 1 Extraction failed: {e}")
        return []


def score_events(events: list[dict], github_intel: dict) -> list[dict]:
    """
    Stage 2: Evaluate and score extracted events.
    """
    if not events:
        return []

    client = _get_client()
    if not client:
        return []

    # Prepare input payload for Stage 2
    eval_input = {
        "events_to_evaluate": events,
        "github_intelligence": github_intel
    }
    prompt = json.dumps(eval_input, indent=2)
    log.info(f"Stage 2: Scoring {len(events)} events with GitHub intelligence...")

    try:
        response = client.models.generate_content(
            model=MODEL_NAME,
            contents=prompt,
            config=types.GenerateContentConfig(
                system_instruction=STAGE_2_INSTRUCTION,
                response_mime_type="application/json",
                response_schema=ScoringResult,
                temperature=TEMPERATURE,
            ),
        )

        try:
            parsed: ScoringResult = response.parsed
            scored = [e.model_dump() for e in parsed.events]
        except (AttributeError, Exception):
            data = json.loads(response.text)
            scored = data.get("events", data if isinstance(data, list) else [])

        log.info(f"Stage 2: Scored {len(scored)} events successfully")
        return scored

    except Exception as e:
        log.error(f"Stage 2 Scoring failed: {e}")
        # Return fallback scored items with default scores if it crashes
        fallback_scored = []
        for e in events:
            # Simple fallback structure
            fallback_scored.append({
                **e,
                "prize_breakdown": "N/A",
                "sponsor_analysis": "N/A",
                "sponsor_quality": 5.0,
                "hiring_potential": 5.0,
                "startup_potential": 5.0,
                "prize_score": 5.0,
                "networking_potential": 5.0,
                "easy_winning_potential": 5.0,
                "easy_winning_analysis": "Default fallback score due to evaluation error.",
                "fos_score": 5.0,
                "fos_verdict": "⚠️",
                "networking_analysis": "N/A",
                "career_upside": "N/A",
                "competition_analysis": "N/A",
                "best_categories": ["Software Project"],
                "roi_analysis": "N/A",
                "recommendation": "ONLY IF FREE",
                "why_relevant": "Fallback scored event."
            })
        return fallback_scored
