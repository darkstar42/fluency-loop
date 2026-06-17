# Teaching workspace — agent guide

This repository is a **teaching workspace** for improving spoken fluency in *any*
language the user is learning. The teaching method lives in the bundled `/teach`
skill (`.claude/skills/teach/`); the speech analyzer in `scripts/` adapts to the
chosen language.

## First run

When a session starts, check `MISSION.md`. If it still contains the
"_Not yet populated_" placeholder, the user is new here. Tell them to run:

```
/teach
```

`/teach` cannot be triggered automatically (it's user-invoked by design), so the
first move is to point the user at it.

### Onboarding: establish the language first

As part of that first `/teach` session, before building any lessons, find out:

1. **Which language they want to learn to speak** (the target).
2. **Their native language(s)** — this drives which pronunciation module applies.

Then write `config.json` at the repo root (copy `config.example.json`):

```json
{ "target_language": "en", "native_language": "de" }
```

Use `en` or `ja` for the full fluency adapters (words / morae); use `generic` for
any other language (whitespace-word fluency still works). The analyzer reads this
file. Then proceed with the mission interview and lessons as described in
`.claude/skills/teach/SKILL.md`, grounding everything in the chosen language.

## Start of every session (do this automatically)

A new session has no memory of the last one. So at the **start of every session**,
before anything else:

1. Read `MISSION.md`, the `learning-records/`, and `NOTES.md` (especially the
   "RESUME HERE" block).
2. Find the **last-seen take id** recorded in `NOTES.md`, then run
   `scripts/analyze.sh --since <last-seen-id>`. It reads the target language from
   `config.json` and analyzes only takes in that language (skipping the user's
   other-language dictation in the shared Handy history). This sweeps in
   *everything* they dictated in the target language since you last looked —
   including everyday usage between lessons, not just prompted practice.
3. Use your judgment on the results: surface what's actionable, keep it
   encouraging, don't dump raw metrics. Turn patterns into the next lesson.
4. **Update the last-seen id** in `NOTES.md` to the newest take you analyzed, so
   the next session resumes cleanly.

This watermark is what makes between-lesson usage get analyzed automatically. If
`NOTES.md` has no last-seen id yet (fresh workspace), analyze the most recent
takes (`scripts/analyze.sh --last 10`) and record the highest id you saw.

## The practice loop

1. You give a speaking prompt.
2. The user speaks the answer into the **Handy** speech-to-text app (one take,
   no editing — the natural hesitations are the signal).
3. You read the new takes from Handy's database and run the analyzer, then give
   targeted, encouraging feedback. Track flow (speed, pausing, length of unbroken
   runs), not error count.

**Not just prompted practice.** Handy's history also holds the user's everyday
dictation — messages, notes, work emails, AI prompts. That ambient usage is real
spontaneous speech and is often the truest signal of how they speak under no
pressure, so analyze *all* new takes in the target language, not only answers to
your prompts. When it matters, distinguish deliberate practice rounds (e.g.
same-topic monologue repetitions) from general dictation — but mine both for
patterns to teach from.

## The analyzer (`scripts/`)

Run the whole offline suite on new takes:

```
scripts/analyze.sh --since <last-seen-id>     # fluency (+ pronunciation if target is English)
scripts/analyze.sh --ids 805,806,807
```

It reads Handy's `history.db` and the matching `.wav` recordings from
`~/Library/Application Support/com.pais.handy/` (macOS), and picks the language
from `config.json`. See `README.md` for one-time setup (Python venv + ffmpeg) and
what each script reports.

> If only ~5 takes are ever available, the user likely hasn't raised Handy's
> history limit (default 5). Point them to the README setup step to increase it.

**Fluency** (`fluency.py`) works for every language — the audio metrics are
language-neutral and only the counting unit changes (words / morae / …, via
`scripts/lang.py`). **Pronunciation** (`probe.py`, `pron_align.py`) is the
**English-from-German** reference module: it runs only when `target_language` is
`en`, and its transfer flags assume a German L1 (`GER_TARGETS` in those scripts).
To support another target language or L1, add an adapter in `lang.py` and/or a
pronunciation module modeled on the English one.

## Conventions

- Keep `MISSION.md`, `RESOURCES.md`, `NOTES.md`, `learning-records/`, `lessons/`,
  and `reference/` updated per the format docs in `.claude/skills/teach/`.
- Lessons are self-contained, beautiful, printable HTML in `lessons/`.
- Numbered files (`learning-records/`, `lessons/`) increment: `0001-`, `0002-`, …
