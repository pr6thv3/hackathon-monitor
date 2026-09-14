# 🎯 Hackathon & Opportunity Intelligence Agent (v4)

A personalized, resilient opportunity scout that continuously discovers, evaluates, and delivers high-value hackathons, competitions, workshops, and student opportunities across **7+ major platforms and college portals**.

Built on a **5-stage AI pipeline** with dual evaluation frameworks (**Founder Opportunity Score [FOS]** for global platforms and **Student Opportunity Score [SOS]** for campus portals), natural language interest profiling, and mobile-optimized Telegram alerts — running 100% free forever ($0/month).

---

## What's New in v4

- 🔗 **Guaranteed Real URLs**: Devpost API integration and structured DOM card parsing eradicate null hyperlinks (was 93% broken).
- 🎓 **Student Opportunity Score (SOS)**: College-focused rubric (Learning Value, Skill Building, Network, Competition, Career) ensures campus events (e.g. CODELYMPICS, Make-A-Thon) aren't penalized for lacking VC judges or Fortune 500 sponsors.
- 🏷️ **Expanded 11-Category Taxonomy**: Supports hackathons, competitions, workshops, bootcamps, conferences, seminars, hiring challenges, buildathons, internships, open source bounties, and pitch competitions.
- 🎯 **Natural Language Personalization**: State your interests freely in `config.yaml` (e.g., *"I want AI hackathons and robotics contests, not generic seminars"*); the AI resolves a structured `PreferenceProfile` and generates a direct match explanation for every alert.
- 🛡️ **Batch Scoring & Zero Poison**: Event scoring runs in chunks of ≤5 events. Any batch failure is skipped rather than poisoning memory with 5.0 flat fallbacks. Strict Pydantic `Literal` validation rejects malformed verdicts.
- ⚡ **Mobile-Optimized Telegram Alerts**: High-impact alerts under 350 characters with urgency badges (⚡ ≤7d, 🔥 ≤30d, 📌 >30d), match percentages, and direct registration buttons. Capped at 3 items to eliminate notification fatigue.
- 🏛️ **Pluggable College Adapters**: Modular `CollegePortalAdapter` architecture with session cookie caching (`auth_state_vit.json`) to prevent repeated logins and account lockout risks.
- 🗄️ **Relational Database & 90-day TTL**: SQLite (`data/monitor.db`) tracks historical events, user feedback, and scores, while pruning stale records older than 90 days and auto-syncing active items to `seen_events.json` for CI/CD compatibility.
- 🔒 **Prompt Injection Defense**: Sanitizes scraped web content, strips override tags, and encloses untrusted text in strict delimiters.

---

## 5-Stage AI Intelligence Pipeline

```
Ingestion Layer (Devpost, Devfolio, Unstop, HackerEarth, DoraHacks, MLH, College Adapters)
  ↓
Stage 1: Gemini Extraction (Sanitized content → 11-category taxonomy + guaranteed URLs)
  ↓
Deduplication & TTL Pruning (Check SQLite & seen_events.json; prune >90 days)
  ↓
Stage 2: Dual Scoring & GitHub Scan (FOS for global platforms, SOS for campus portals; batches ≤5)
  ↓
Stage 3: Relevance Scoring (Evaluate against user's natural language PreferenceProfile)
  ↓
Stage 4: Composite Ranking (relevance × urgency × link_penalty + adaptive quality gates)
  ↓
Stage 5: Notification Delivery (Max 3 concise Telegram alerts + Markdown digest report)
  ↓
Persistence: Record in SQLite & sync active subset to seen_events.json for Git auto-commit
```

---

## Evaluated Frameworks

### 1. Student Opportunity Score (SOS) — College Portals
- **Learning Value (30%)**: Mentorship, curriculum depth, hands-on development.
- **Skill Building (25%)**: Portfolio-grade project, demonstrable tech stack.
- **Network Value (20%)**: Peer builders, club leads, alumni.
- **Competitive Achievement (15%)**: Prizes, trophies, IEEE/ACM recognition.
- **Career Relevance (10%)**: Placement advantage and resume impact.
- *Quality Gate:* `SOS >= 3.0` and verdict != `❌`.

### 2. Founder Opportunity Score (FOS) — Global Platforms
- **Sponsor Quality (30%)**: Tier-1 tech firms (OpenAI, AWS, Google) vs others.
- **Hiring Potential (25%)**: Sponsor fast-tracks, recruitment pipelines, bounties.
- **Startup Potential (20%)**: VC judges, accelerator passes, equity-free grants.
- **Prize Pool (15%)**: Cash prizes and cloud credits.
- **Networking (10%)**: Global builder community, top mentors.
- *Quality Gate:* `FOS >= 5.0` and verdict != `❌`.

### 3. Easy-Win Potential (1.0 to 10.0)
Evaluates friction funnels (selection rounds, mandatory demo videos, niche API tracks raise dedicated builders' win probabilities by eliminating low-effort entries).

---

## Configuration (`config.yaml`)

Edit `config.yaml` to customize your profile, college portal, and notification rules:

```yaml
user:
  name: Preethve

portals:
  - id: vit_eventhub
    name: VIT Chennai EventHub
    url: https://eventhubcc.vit.ac.in/EventHub/mainDashboard
    adapter: vit_eventhub
    auth:
      type: form_login
      username_env: VIT_USERNAME
      password_env: VIT_PASSWORD

preferences: |
  I am an engineering student at VIT interested in AI/ML, autonomous agents,
  robotics, systems programming, and competitive hackathons.
  I prioritize hands-on building, practical coding competitions, and hackathons
  offering prize pools, mentorship, or career upside.
  Exclude purely non-technical seminars or passive lecture-only sessions.

notifications:
  channel: telegram
  max_per_run: 3
  digest_mode: true
```

---

## Setup & Running

### 1. Prerequisites
- Google AI Studio Gemini API Key (`GEMINI_API_KEY`)
- Telegram Bot Token & Chat ID (`TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`)
- GitHub Personal Access Token (`GH_PAT` / `GITHUB_TOKEN`, optional)
- College portal credentials (optional, e.g. `VIT_USERNAME`, `VIT_PASSWORD`)

### 2. Local Installation & Testing

```bash
# Clone the repository
git clone https://github.com/pr6thv3/hackathon-monitor.git
cd hackathon-monitor

# Create virtual environment & install dependencies
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/playwright install chromium --with-deps

# Configure environment variables
cp .env.example .env
# Edit .env with your keys

# Run automated tests
.venv/bin/pytest tests/ -v

# Run the pipeline locally (use --dry-run to test without sending alerts)
.venv/bin/python main.py --dry-run
```

### 3. Command Line Flags

- `--force`: Bypass memory deduplication and force re-evaluation of all scraped opportunities.
- `--dry-run`: Run complete extraction, scoring, and ranking without dispatching Telegram alerts.
- `--config <path>`: Specify an alternate configuration YAML file (default: `config.yaml`).

---

## Project Structure

```
├── config.yaml                      # User profile & portal preferences
├── data/
│   └── monitor.db                   # Relational SQLite database
├── src/
│   ├── adapters/
│   │   ├── base.py                  # CollegePortalAdapter abstract base class
│   │   ├── vit.py                   # VIT EventHub adapter with session caching
│   │   └── generic.py               # Generic Playwright card adapter
│   ├── brain.py                     # Multi-stage AI pipeline (SOS/FOS/Relevance)
│   ├── config.py                    # YAML config loader & preference resolver
│   ├── db.py                        # SQLite engine & JSON sync
│   ├── feedback.py                  # User feedback & weight modulation
│   ├── fetcher_college.py           # College adapter gateway
│   ├── fetcher_devfolio.py          # Devfolio API + Playwright
│   ├── fetcher_devpost.py           # Devpost API + DOM card extraction
│   ├── fetcher_dorahacks.py         # DoraHacks API + Playwright
│   ├── fetcher_hackerearth.py       # HackerEarth upcoming API + Playwright
│   ├── fetcher_mlh.py               # MLH static HTML scraper
│   ├── fetcher_unstop.py            # Unstop API + Playwright
│   ├── github_intel.py              # GitHub ecosystem scanner
│   ├── health.py                    # Source health tracker & metrics
│   ├── memory.py                    # Deduplication & 90-day TTL expiry
│   ├── notifier.py                  # Mobile-optimized Telegram delivery
│   └── report.py                    # Markdown digest report generator
├── tests/                           # Pytest unit & integration test suite
├── reports/                         # Locally generated Markdown digest reports
├── main.py                          # Main pipeline orchestrator
├── seen_events.json                 # Auto-committed deduplication memory
└── requirements.txt                 # Dependencies
```

---

## Running Costs

| Component | Cost | Notes |
|---|---|---|
| Playwright Scrapers | Free | Headless Chromium in local/GitHub runner |
| API Integrations | Free | Public/open endpoints (Devpost, Devfolio, Unstop, DoraHacks, HackerEarth, MLH) |
| Gemini 2.5 Flash | Free | Free tier API key |
| GitHub REST API | Free | 60 req/hr unauthenticated; 5,000 req/hr with PAT |
| Telegram Bot API | Free | Unlimited alerts |
| GitHub Actions | Free | Under 200 min/month of 2,000 free runner minutes |

**Total: $0/month, forever.**
