# 🎯 Hackathon & Workshop Monitor

Automated pipeline that scrapes **Devpost**, **Devfolio**, and **VIT EventHub** for all tech hackathons and workshops, filters them through **Gemini AI**, and sends curated alerts to your **Telegram** — for **$0/month, forever**.

## Architecture

```
⏰ GitHub Actions (9:00 AM + 6:00 PM IST)
  ├── 🕷️ Devpost       → Playwright (headless Chromium)
  ├── 🕷️ Devfolio      → Internal API + Playwright fallback
  └── 🕷️ VIT EventHub  → Playwright + login automation
         ↓
  🧠 Gemini 2.5 Flash  → Extract all tech events + portfolio evaluation
         ↓
  💾 seen_events.json   → Deduplicate (SHA-256 title hash)
         ↓
  📱 Telegram Bot       → Only when new matches found
```

## What Gets Detected

The AI extracts **all tech-related events** including: AI/ML, web dev, mobile, blockchain, cybersecurity, IoT, robotics, game dev, data science, cloud, DevOps, open source, fintech, AR/VR, embedded systems, competitive programming, UI/UX, and more.

Each match includes a **portfolio standout evaluation**.

## Setup

### 1. Prerequisites

- A private GitHub repository
- API keys: Gemini, Telegram Bot
- VIT EventHub credentials

### 2. GitHub Secrets

Navigate to your repo → **Settings** → **Secrets and variables** → **Actions** → **New repository secret**:

| Secret Name | Value |
|------------|-------|
| `GEMINI_API_KEY` | Your Google AI Studio API key |
| `TELEGRAM_BOT_TOKEN` | Your Telegram bot token from @BotFather |
| `TELEGRAM_CHAT_ID` | Your Telegram chat ID from @userinfobot |
| `VIT_USERNAME` | Your VIT registration number or email |
| `VIT_PASSWORD` | Your VIT password |

### 3. Local Testing

```bash
# Clone the repo
git clone <your-repo-url>
cd hackathon-monitor

# Create .env from template
cp .env.example .env
# Edit .env with your actual keys

# Install dependencies
pip install -r requirements.txt
playwright install chromium --with-deps

# Run the pipeline
python main.py
```

### 4. Deploy

Push to GitHub. The workflow runs automatically at **9:00 AM and 6:00 PM IST** daily.

To trigger manually: **Actions** tab → **Hackathon & Workshop Monitor** → **Run workflow**.

## Project Structure

```
├── .github/workflows/schedule.yml   # Twice-daily cron + CI
├── src/
│   ├── fetcher_devpost.py           # Playwright scraper
│   ├── fetcher_devfolio.py          # API + Playwright fallback
│   ├── fetcher_college.py           # VIT EventHub + login
│   ├── brain.py                     # Gemini AI — all tech events
│   ├── memory.py                    # JSON deduplication
│   └── notifier.py                  # Telegram Bot API
├── main.py                          # Orchestrator
├── seen_events.json                 # Persistent memory (auto-committed)
├── requirements.txt                 # Pinned Python dependencies
└── .env.example                     # Local dev template
```

## Cost

| Component | Cost | Notes |
|-----------|------|-------|
| Playwright | Free | No API limits |
| Gemini 2.5 Flash | Free | ~200+ RPD, uses 2/day |
| Telegram Bot API | Free | Unlimited messages |
| GitHub Actions | Free | ~120 min/month of 2,000 |

**Total: $0/month, forever.**
