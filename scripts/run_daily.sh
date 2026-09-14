#!/usr/bin/env bash
# Hackathon & Opportunity Intelligence Agent — Automated Daily Runner
# Runs the full v4 intelligence pipeline and sends Telegram alerts

set -e

# Navigate to project directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$SCRIPT_DIR"

echo "================================================================="
echo "🚀 Running Automated Daily Opportunity Intelligence Pipeline"
echo "Date: $(date)"
echo "Directory: $SCRIPT_DIR"
echo "================================================================="

# Activate virtual environment and run main pipeline
.venv/bin/python main.py "$@"

echo "================================================================="
echo "✅ Run completed successfully at $(date)"
echo "================================================================="
