# 🎯 Elite Hackathon Opportunity Intelligence Agent v3

Automated intelligence agent that monitors **7 major hackathon sources**, performs **GitHub ecosystem scans**, evaluates opportunities using **Founder Opportunity Scoring (FOS)** and **Easy-Win Potential**, and delivers rich digests and Markdown reports directly to your **Telegram** — all for **$0/month, forever**.

## Architecture & Data Flow

```
⏰ GitHub Actions (9:00 AM + 6:00 PM IST)
  ├── 🕷️ Devpost       → Playwright (headless Chromium)
  ├── 🕷️ Devfolio      → Internal API + Playwright fallback
  ├── 🕷️ Unstop        → Public API + Playwright fallback
  ├── 🕷️ HackerEarth   → Chrome Extension API + Playwright fallback
  ├── 🕷️ DoraHacks     → REST API + Playwright fallback
  ├── 🕷️ MLH           → Requests + BeautifulSoup (Rails static HTML)
  └── 🕷️ VIT EventHub  → Playwright + login automation (College Hackathons only)
         ↓
  🧠 Stage 1: Gemini 2.5 Flash  → Extract all tech-related hackathons/workshops
         ↓
  💾 Deduplication Check        → Skip already-seen event titles
         ↓
  🐙 GitHub Community Scan      → Query repo stars, good first issues, sponsor bounties
         ↓
  🧠 Stage 2: Gemini 2.5 Flash  → Calculate FOS score + Easy-Win Potential
         ↓
  ⚖️ Quality Gate Filter        → Keep if FOS >= 7.0 OR Easy-Win >= 7.0
         ↓
  📊 Report Generator           → Create a detailed, professional Markdown report file
         ↓
  📱 Telegram Bot Delivery      → Send HTML summary + attach the full Markdown report
```

## Evaluated Metrics

For each newly discovered event, the AI agent performs two analyses:
1. **Founder Opportunity Score (FOS) (Weighted 10-point scale)**:
   - **Sponsor Quality (30%)**: Tier 1 tech firms (AWS, Google, Vercel, OpenAI) vs others.
   - **Hiring Potential (25%)**: Sponsor fast-tracks, resume drops, active recruitment.
   - **Startup Potential (20%)**: Accel passes, VCs, pilot grants, founder tracks.
   - **Prize Pool (15%)**: Cash prizes and track bounties.
   - **Networking (10%)**: Judges, mentors, and high-profile offline venues.
2. **Easy-Win Potential (10-point scale)**:
   - Evaluates win probability by examining target niche (e.g. college-only, local offline events), total track categories, and expected competition size.

## Setup

### 1. Prerequisites
- A private GitHub repository.
- Google AI Studio Gemini API Key.
- Telegram Bot Token & Chat ID.
- GitHub Personal Access Token (PAT) (Optional, highly recommended for rate limits).
- VIT Student Portal credentials (for college hackathons).

### 2. GitHub Secrets
Navigate to your repository → **Settings** → **Secrets and variables** → **Actions** → **New repository secret**:

| Secret Name | Value | Required | Purpose |
|------------|-------|----------|---------|
| `GEMINI_API_KEY` | Your Google AI Studio API key | Yes | Two-stage Gemini evaluation |
| `TELEGRAM_BOT_TOKEN` | Your Telegram bot token | Yes | Notification delivery |
| `TELEGRAM_CHAT_ID` | Your Telegram chat ID | Yes | Chat destination |
| `VIT_USERNAME` | Your VIT registration number/email | Yes | College portal login |
| `VIT_PASSWORD` | Your VIT password | Yes | College portal login |
| `GH_PAT` | Your GitHub Personal Access Token | No | Higher GitHub API limits |

### 3. Local Testing

```bash
# Clone the repository
git clone <your-repo-url>
cd hackathon-monitor

# Create .env from the template
cp .env.example .env
# Edit .env and fill in your actual credentials

# Install dependencies
pip install -r requirements.txt
playwright install chromium --with-deps

# Run the pipeline locally
python main.py
```

### 4. Deployment
Push the code to your private GitHub repository. The Actions workflow runs automatically at **9:00 AM and 6:00 PM IST** daily.

To run it manually: Go to the **Actions** tab → **Hackathon & Workshop Monitor** → **Run workflow**.

## Project Structure

```
├── .github/workflows/schedule.yml   # Twice-daily cron workflow
├── src/
│   ├── fetcher_devpost.py           # Devpost Playwright scraper
│   ├── fetcher_devfolio.py          # Devfolio API + Playwright
│   ├── fetcher_unstop.py            # Unstop API + Playwright
│   ├── fetcher_hackerearth.py       # HackerEarth API + Playwright
│   ├── fetcher_dorahacks.py         # DoraHacks API + Playwright
│   ├── fetcher_mlh.py               # MLH static HTML scraper
│   ├── fetcher_college.py           # VIT EventHub login scraper
│   ├── github_intel.py              # GitHub API community details
│   ├── brain.py                     # Two-stage Gemini scoring
│   ├── report.py                    # Markdown report formatting
│   ├── memory.py                    # SHA-256 JSON memory deduplication
│   └── notifier.py                  # Telegram HTML & Document notifier
├── reports/                         # Locally stored reports (Git-ignored)
├── main.py                          # Main orchestrator pipeline
├── seen_events.json                 # Deduplication memory (auto-committed)
├── requirements.txt                 # Pinned dependencies
└── .env.example                     # Local development template
```

## Running Costs ($0/month)

| Component | Cost | Notes |
|-----------|------|-------|
| Playwright Scrapers | Free | Local rendering inside runner |
| API integrations | Free | No credit walls (MLH, Devfolio, DoraHacks, HackerEarth) |
| Gemini 2.5 Flash | Free | Free tier API key (2 calls per pipeline run) |
| GitHub Search API | Free | Free API queries (30 reqs/min with PAT) |
| Telegram Bot API | Free | Unlimited message & document delivery |
| GitHub Actions | Free | Under 150 minutes/month of the 2,000 free minutes |

**Total: $0/month, forever.**
