# 🎯 Hackathon & Opportunity Intelligence Agent (v4)

A personalized, resilient opportunity scout that continuously discovers, evaluates, and delivers high-value hackathons, competitions, workshops, and student opportunities across **7+ major platforms and college portals**.

Built on a **5-stage AI pipeline** with dual evaluation frameworks (**Founder Opportunity Score [FOS]** for global platforms and **Student Opportunity Score [SOS]** for campus portals), natural language interest profiling, dynamic user feedback reinforcement, Groq 120B / Gemini multi-model support, and mobile-optimized Telegram alerts — running 100% free forever ($0/month).

---

## 🚀 Key Features in v4

- ⚡ **Parallel Multi-Source Ingestion**: Fetches from Devpost, Devfolio, Unstop, HackerEarth, DoraHacks, MLH, and VIT EventHub concurrently, cutting ingestion latency by **70%+** (~11 seconds total).
- 🧠 **Multi-Model LLM Engine (Groq 120B & Gemini 2.5)**: Natively supports **Groq LPU hardware (`openai/gpt-oss-120b` / `llama-3.3-70b`)** with automatic failover to **Gemini 2.5 Flash**.
- 🎓 **Student Opportunity Score (SOS)**: College-focused rubric (Learning Value, Skill Building, Network, Competition, Career) ensures campus events (e.g. CODELYMPICS, Make-A-Thon) aren't penalized for lacking VC judges or Fortune 500 sponsors.
- 💼 **Founder Opportunity Score (FOS)**: Global platform rubric (Sponsor Quality, Hiring Upside, Startup/VC Grants, Prize Pool, Builder Community).
- 📈 **Blended Composite Ranking Formula**: Evaluates opportunities balancing user relevance (50%), opportunity score (30%), win probability (20%), urgency multipliers, and registration link availability penalties:
  $$\text{Composite Rank} = (0.5 \times \text{Relevance} + 0.3 \times \text{OppScore} + 0.2 \times \text{EasyWin}) \times \text{Urgency} \times \text{LinkPenalty}$$
- 🔄 **User Feedback Reinforcement Loop**: Dynamic `FeedbackProcessor` records engagement (`applied`, `opened`, `dismissed`) to modulate future AI relevance scores over time.
- ⚡ **Mobile-Optimized Telegram Alerts & Markdown Reports**: Concise alerts under 350 characters with urgency badges (⚡ ≤7d, 🔥 ≤30d, 📌 >30d) plus formatted Markdown digest reports in `reports/`.
- 🏛️ **Pluggable College Adapters**: Modular `CollegePortalAdapter` architecture with session cookie caching (`auth_state_vit.json`) to prevent repeated logins.
- 🗄️ **Relational Database & 90-day TTL**: SQLite (`data/monitor.db`) tracks historical events and user scores, pruning stale records >90 days and auto-syncing to `seen_events.json` for CI/CD compatibility.

---

## ⚙️ GitHub Actions Scheduled Workflow & Automation Setup

The project includes an automated, configurable GitHub Actions workflow ([`.github/workflows/schedule.yml`](file:///.github/workflows/schedule.yml)) that runs on a defined cron schedule.

### 1. How to Configure GitHub Repository Secrets

To enable live AI scoring and Telegram notification delivery in GitHub Actions:

1. Navigate to your repository on GitHub: `https://github.com/pr6thv3/hackathon-monitor`.
2. Go to **Settings** > **Secrets and variables** > **Actions**.
3. Click **New repository secret** and add the following secrets:

| Secret Name | Description | Required? |
|---|---|---|
| `GROQ_API_KEY` | Groq API Key (from [console.groq.com](https://console.groq.com/)) | Recommended (Blazing fast) |
| `GEMINI_API_KEY` | Google Gemini API Key (from [aistudio.google.com](https://aistudio.google.com/)) | Recommended (Primary/Fallback) |
| `TELEGRAM_BOT_TOKEN` | Bot token from Telegram `@BotFather` | Required for Telegram alerts |
| `TELEGRAM_CHAT_ID` | Your Chat ID from Telegram `@userinfobot` | Required for Telegram alerts |
| `VIT_USERNAME` | VIT Student Registration Number / Username | Optional (Campus events) |
| `VIT_PASSWORD` | VIT Portal Password | Optional (Campus events) |
| `GH_PAT` | Personal Access Token with repo scope | Optional (Raises API limits) |

### 2. How to Customize the Scheduled Cron Timing

The schedule is defined in [`.github/workflows/schedule.yml`](file:///.github/workflows/schedule.yml). To change when it runs:

```yaml
on:
  schedule:
    # Change the cron string below (UTC time)
    # Example: '0 8 * * *' = Daily at 8:00 AM UTC (1:30 PM IST)
    # Example: '0 0 * * 1' = Every Monday at Midnight UTC
    - cron: '0 8 * * *'
  workflow_dispatch: {}     # Manual trigger button in GitHub Actions UI
```

### 3. Manual On-Demand Execution

You can run the pipeline on demand anytime:
1. Go to **Actions** tab in GitHub.
2. Select **Scheduled Hackathon & Opportunity Intelligence Agent**.
3. Click **Run workflow** > **Run workflow**.

---

## 5-Stage AI Intelligence Pipeline

```
Ingestion Layer (Devpost, Devfolio, Unstop, HackerEarth, DoraHacks, MLH, College Adapters)
  ↓
Stage 1: Multi-Model Extraction (Sanitized source chunks → 11-category taxonomy + guaranteed URLs)
  ↓
Deduplication & TTL Pruning (Check SQLite & seen_events.json; prune >90 days)
  ↓
Stage 2: Dual Scoring & GitHub Scan (FOS for global platforms, SOS for campus portals; batches ≤5)
  ↓
Stage 3: Personalized Relevance & Feedback Modulation (Evaluate against PreferenceProfile & feedback weights)
  ↓
Stage 4: Blended Composite Ranking ((0.5×Rel + 0.3×OppScore + 0.2×EasyWin) × Urgency × LinkPenalty)
  ↓
Stage 5: Notification Delivery & GitHub Summary (Telegram alerts + GitHub Step Summary + Markdown report)
  ↓
Persistence: Record in SQLite & sync active subset to seen_events.json for Git auto-commit
```

---

## Local Installation & CLI Usage

### 1. Prerequisites
- Python 3.10+
- Groq API Key (`GROQ_API_KEY`) or Gemini API Key (`GEMINI_API_KEY`)
- Telegram Bot Token & Chat ID (`TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`)

### 2. Local Setup

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

# Run unit & integration test suite (29 tests)
.venv/bin/pytest tests/ -v

# Run the pipeline locally (use --dry-run to test without sending alerts)
.venv/bin/python main.py --dry-run
```

### 3. CLI Utilities & Commands

```bash
# View system metrics & feedback counts
.venv/bin/python main.py --stats

# List recent top opportunities stored in database
.venv/bin/python main.py --list-events

# Record user feedback on an event (applied, opened, bookmarked, dismissed)
.venv/bin/python main.py --feedback 12 applied

# Force re-evaluation of all events (bypass memory deduplication)
.venv/bin/python main.py --force --dry-run
```

---

## Project Structure

```
├── .github/
│   └── workflows/
│       ├── schedule.yml             # Scheduled cron & workflow dispatch pipeline
│       └── test.yml                 # Automated Pytest CI/CD workflow
├── config.yaml                      # User profile & portal preferences
├── data/
│   └── monitor.db                   # Relational SQLite database (ignored from Git)
├── scripts/
│   └── run_daily.sh                 # Local automated daily runner script
├── src/
│   ├── adapters/
│   │   ├── base.py                  # CollegePortalAdapter abstract base class
│   │   ├── vit.py                   # VIT EventHub adapter with session caching
│   │   └── generic.py               # Generic Playwright card adapter
│   ├── brain.py                     # Multi-model AI pipeline (Groq 120B / Gemini)
│   ├── config.py                    # YAML config loader & LLM preference parser
│   ├── db.py                        # SQLite relational engine & JSON sync
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
├── tests/                           # Pytest test suite (29 unit & E2E tests)
├── reports/                         # Locally generated Markdown digest reports
├── main.py                          # Main orchestrator & CLI entry point
├── seen_events.json                 # Auto-committed deduplication memory
└── requirements.txt                 # Dependencies
```

---

## Running Costs

| Component | Cost | Notes |
|---|---|---|
| Playwright Scrapers | Free | Headless Chromium in local/GitHub runner |
| Public API Ingestion | Free | Devpost, Devfolio, Unstop, DoraHacks, HackerEarth, MLH |
| Groq Cloud API | Free | 30 RPM / 14,400 RPD free tier |
| Gemini 2.5 Flash API | Free | Free tier API key |
| Telegram Bot API | Free | Unlimited alerts |
| GitHub Actions | Free | Under 200 min/month of 2,000 free runner minutes |

**Total Cost: $0/month, forever.**
