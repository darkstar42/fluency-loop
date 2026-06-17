#!/usr/bin/env bash
# One-time setup for the analyzer: create the virtualenv and install dependencies.
# Requires Python 3.12 and ffmpeg/ffprobe on PATH (brew install ffmpeg).
set -euo pipefail
DIR="$(cd "$(dirname "$0")" && pwd)"

if ! command -v ffmpeg >/dev/null 2>&1; then
  echo "⚠️  ffmpeg not found on PATH. Install it first:  brew install ffmpeg"
fi

PYTHON="${PYTHON:-python3}"
echo "Creating venv at $DIR/.venv using $($PYTHON --version)…"
"$PYTHON" -m venv "$DIR/.venv"

echo "Installing dependencies (this pulls torch et al. — can take a few minutes)…"
"$DIR/.venv/bin/pip" install --upgrade pip
"$DIR/.venv/bin/pip" install -r "$DIR/requirements.txt"

echo
echo "✅ Done. First run of the pronunciation tools downloads the Allosaurus model once, then works offline."
echo "Try:  scripts/analyze.sh --last 3"
