# Spoken-English Teaching Workspace

An AI English teacher that runs in [Claude Code](https://claude.com/claude-code).
It interviews you about *why* you want to improve your spoken English, then builds
short, beautiful, printable lessons grounded in that goal — and measures your real
spontaneous speech with a fully offline audio analyzer.

This is a **blank starter**: no lessons, no learner data. Your first session
creates everything from your own mission.

---

## How it works

You practice by **speaking**, not typing. The teacher gives you a prompt; you
speak your answer (one take, no editing) into a speech-to-text app called
**[Handy](https://github.com/cjpais/Handy)**. The teacher then reads your real
transcripts *and* analyzes the audio — speech rate, pauses, length of unbroken
runs, pronunciation — and turns the patterns into your next lesson. Progress is
tracked as **flow**, not error count, so it stays low-stress.

Everything is local: lessons are HTML files in `lessons/`, your mission and notes
are markdown at the repo root, and the analyzer never sends audio anywhere.

## Quick start

1. **Open this folder in Claude Code.**
2. **Run the teacher:**
   ```
   /teach
   ```
   On a fresh clone `MISSION.md` is empty, so the teacher's first job is to
   interview you and write it. From there, follow along — it'll build your first
   lesson and open it in your browser.

That's all you need to begin lessons. Set up the analyzer below when you're ready
to practice with spoken feedback.

## Setting up the speech analyzer (optional but recommended)

The analyzer reads spoken takes recorded by Handy and reports the metrics that
actually predict perceived fluency.

**Prerequisites (macOS):**
- [Handy](https://github.com/cjpais/Handy) — the speech-to-text app. It stores a
  history database and `.wav` recordings under
  `~/Library/Application Support/com.pais.handy/`, which the scripts read.
  - **Raise the history limit first.** Handy keeps only the **last 5** takes by
    default, so the analyzer would never see more than your 5 most recent
    recordings. In Handy's settings, increase the history size to something large
    (1000 works well) so older practice takes stick around to compare against.
- `ffmpeg` / `ffprobe` — `brew install ffmpeg`
- Python 3.12

**One-time install:**
```bash
scripts/setup.sh          # creates scripts/.venv and installs dependencies
```
The first run of the pronunciation tools downloads the Allosaurus model once,
then everything works offline.

**Run it** (the teacher does this for you each session, but you can too):
```bash
scripts/analyze.sh --last 3            # the 3 most recent takes
scripts/analyze.sh --since 120         # everything newer than take id 120
scripts/analyze.sh --ids 121,122,123   # specific takes
```

### What each script reports
| Script | What it gives you |
|---|---|
| `fluency.py` | words, fillers, duration, **phonation ratio**, **speech rate (wpm)**, pause count/length, **mean length of run** (words per unbroken stretch) — plus a flow-trend table across takes |
| `probe.py` | disfluency typing, **prosody** (pitch range / monotone via Praat), raw phone recognition |
| `pron_align.py` | expected (CMUdict) vs. actual (Allosaurus) phones aligned → **L1-transfer flags** |
| `analyze.sh` | runs all three at once — the standing per-session command |

### First language other than German?
The pronunciation flags default to **German→English** transfer patterns
(th-stopping, w/v, final-obstruent devoicing, æ→ɛ, …). To target a different L1,
edit the `GER_TARGETS` map in `scripts/probe.py` and the flag logic in
`scripts/pron_align.py`. The fluency metrics (`fluency.py`) are language-neutral
and need no changes.

## What's in here

```
MISSION.md          Why you're learning — the compass for every lesson (start empty)
RESOURCES.md        Trusted sources the teacher curates (start empty)
NOTES.md            Teacher's scratchpad + where to resume (start empty)
learning-records/   Decision-grade insights about your progress (ADR-style)
lessons/            Your lessons — self-contained printable HTML
reference/          Cheat-sheets distilled from lessons
scripts/            The offline speech analyzer + setup
.claude/skills/teach/   The teaching method (the /teach skill), bundled in
```

## Privacy

Your mission, notes, lessons, and learning records are written into this repo as
you go — they're personal. If you push this to a **public** GitHub repo, keep that
in mind. The analyzer reads Handy's local database and audio on your machine and
sends nothing to any server.
